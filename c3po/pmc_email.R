library('data.table')
library('rentrez')
library('stringr')
library('xml2')
library('RPostgres')
library('DBI')
library('foreach')

# get PMCID from pmdb

con = dbConnect(RPostgres::Postgres(), dbname = 'pmdb', host = 'localhost')
dt = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'pmc\' ORDER BY pmid DESC limit 10000;'))
dtDOI = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'doi\';'))
dtEmails = setDT(DBI::dbGetQuery(con, 'SELECT email_doi.email, email_doi.doi, article_info.pmid FROM email_doi as email_doi LEFT JOIN article_info as article_info ON email_doi.doi = article_info.doi;'))
dtEmails = dtEmails[, pmid := as.integer(pmid)]

apiKeyFilename = 'c3po/api_key.csv'

apiKey = NA

if (file.exists(apiKeyFilename)) {
  dtAPI = fread(apiKeyFilename)
  apiKey = dtAPI$api_key
}



chunkSize = 50

numChunks = nrow(dt) %/% chunkSize

dtNew = foreach(i = 0:(numChunks-1), .combine = rbind) %do% {
  startNum = (i * chunkSize) + 1
  endNum = startNum + chunkSize - 1
  dtTmp = dt[startNum:endNum,]
  if (is.na(apiKey)) {
    a1 = entrez_fetch(db = 'pmc', id = dtTmp$id_value, rettype = 'xml')
  } else {
    a1 = entrez_fetch(db = 'pmc', id = dtTmp$id_value, rettype = 'xml', api_key = apiKey)
  }
  a2 = read_xml(a1)
  # write_xml(a2, paste0(i, 'chunk_', chunkSize, 'chunkSize_entrez.xml'))
  articles = xml_find_all(a2, './/article')
  articleIds = xml_text(xml_find_all(articles, './/article-id[@pub-id-type=\'pmc\']'))
  if (length(articleIds) < length(articles) ) print(i)
  
  texts1 = xml_text(xml_find_all(xml_find_all(articles, './/author-notes'), './/email'))
  texts2 = xml_find_all(articles, './/author-notes//email', flatten = FALSE)
  texts3 = lapply(texts2, xml_text)
  
  texts4 = xml_find_all(articles, './/contrib[@contrib-type=\'author\']//email', flatten = FALSE)
  texts5 = lapply(texts4, xml_text)
  
  dt1 = data.table(pmc = articleIds, email = texts3)
  dt1 = dt1[, .(email = unlist(email)), by = pmc]
  dt2 = data.table(pmc = articleIds, email = texts5)
  dt2 = dt2[, .(email = unlist(email)), by = pmc]
  
  rbind(dt1, dt2)
  
  
  
  # dtFound = data.table(pmcid = as.character(NA), email = as.character(NA))
  # for(article in articles){
  #   pmcid = ''
  #   for (id in xml_find_all(article, './/article-id')) {
  #     if (xml_attrs(id)[['pub-id-type']] == 'pmid') pmcid = paste0('PMC', xml_text(id))
  #   }
  #   a3 = xml_text(xml_find_all(xml_find_first(article, './/author-notes'), './/email'))
  #   d = data.table(pmcid = pmcid,
  #                  email = a3)
  #   d = d[!is.na(email)]
  #   a4 = xml_find_all(article, './/contrib')
  #   d2 = data.table(pmcid = pmcid,
  #                  contrib_type = xml_attr(a4, 'contrib-type'),
  #                  email = xml_text(xml_find_first(a4, './/email')))
  #   d2 = d2[contrib_type == 'author' & !is.na(email)]
  #   d2[, contrib_type := NULL]
  #   dtFound = rbind(dtFound, d, d2)
  # }
  # dtFound
}

dtNew[, pmc := paste0('PMC', pmc)]
dtNew[, id_value := pmc]
dtMerge = merge.data.table(dtNew, dt, by = 'id_value')
dtMerge = dtMerge[, id_value := NULL]
dtMerge = merge.data.table(dtMerge, dtDOI, by = 'pmid')
dtMerge = dtMerge[, doi := id_value]
dtMerge2 = dtMerge[!dtEmails, on=.(pmid, email)]


