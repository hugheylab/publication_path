library('data.table')
library('rentrez')
library('stringr')
library('xml2')
library('RPostgres')
library('DBI')
library('foreach')

# get PMCID from pmdb

con = dbConnect(RPostgres::Postgres(), dbname = 'pmdb', host = 'localhost')
dt = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'pmc\' ORDER BY pmid DESC limit 1000;'))
dtEmails = setDT(DBI::dbGetQuery(con, 'SELECT email_doi.email, email_doi.doi, article_info.pmid FROM email_doi as email_doi LEFT JOIN article_info as article_info ON email_doi.doi = article_info.doi;'))

chunkSize = 50

numChunks = nrow(dt) %/% chunkSize

dtNew = foreach(i = 0:(numChunks-1), .combine = rbind) %do% {
  startNum = (i * chunkSize) + 1
  endNum = startNum + chunkSize - 1
  dtTmp = dt[startNum:endNum,]
  a1 = entrez_fetch(db = 'pmc', id = dtTmp$id_value, rettype = 'xml')
  a2 = read_xml(a1)
  # write_xml(a2, paste0(i, 'chunk_', chunkSize, 'chunkSize_entrez.xml'))
  articles = xml_find_all(a2, './/article')
  texts1 = xml_text(xml_find_all(xml_find_all(articles, './/author-notes'), './/email'))
  dtFound = data.table(pmcid = as.character(NA), email = as.character(NA))
  for(article in articles){
    pmcid = ''
    for (id in xml_find_all(article, './/article-id')) {
      if (xml_attrs(id)[['pub-id-type']] == 'pmc') pmcid = paste0('PMC', xml_text(id))
    }
    a3 = xml_text(xml_find_all(xml_find_first(article, './/author-notes'), './/email'))
    d = data.table(pmcid = pmcid,
                   email = a3)
    d = d[!is.na(email)]
    a4 = xml_find_all(article, './/contrib')
    d2 = data.table(pmcid = pmcid,
                   contrib_type = xml_attr(a4, 'contrib-type'),
                   email = xml_text(xml_find_first(a4, './/email')))
    d2 = d2[contrib_type == 'author' & !is.na(email)]
    d2[, contrib_type := NULL]
    dtFound = rbind(dtFound, d, d2)
  }
  dtFound
}


