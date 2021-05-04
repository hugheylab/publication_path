library('data.table')
library('rentrez')
library('stringr')
library('xml2')
library('RPostgres')
library('DBI')
library('foreach')
library('RCurl')
library('glue')
library('stringr')
options(timeout = 900)


# get PMCID from pmdb


# Replace the two below with the pmparser version
getRemoteFilenames = function(url, pattern) {
  raw = RCurl::getURL(url)
  x = strsplit(raw, '\\n')[[1L]]
  m = regexpr(glue('{pattern}$'), x)
  filenames = regmatches(x, m)
  d = data.table(
    tar_filename = filenames)
  d = d[, download_url := paste0(url, tar_filename)]
  return(d)}

download = function(url, destfile, n = 3L) {
  i = 1L
  x = 1L
  while (i <= n && !identical(x, 0L)) {
    x = tryCatch({utils::download.file(url, destfile)}, error = function(e) e)
    if (!identical(x, 0L)) Sys.sleep(stats::runif(1L, 1, 2))
    i = i + 1L}
  
  if (inherits(x, 'error')) stop(x)
  if (x != 0L) stop(glue('Download of {url} failed {n} times. Ruh-roh.'))
  x}

getAndUnzipRemoteFiles = function(localDir, url, pattern) {
  if (!dir.exists(localDir)) {
    dir.create(localDir)
  }
  fNames = getRemoteFilenames(url, pattern)
  fNames[, tar_path := file.path(localDir, tar_filename)]
  setwd(localDir)
  r = foreach(f = iterators::iter(fNames, by = 'row'), .combine = c) %dopar% {
    download(f$download_url, f$tar_filename)
    untar(f$tar_filename)
  }
  setwd('../')
  fileDT = data.table(file_paths = list.files(localDir, recursive = TRUE))
  fileDT[, pmc := str_extract(file_paths, '[ \\w-]+?(?=\\.)')]
  return(fileDT)
}

addTimings = function(timingsDT, stepName) {
  elapsed = proc.time()[['elapsed']]
  timingsDT = rbind(timingsDT, data.table(step = stepName, elapsed = elapsed))
}

dtFromXml = function(articleIds, articles, xpath) {
  nodes = xml_find_all(articles, xpath, flatten = FALSE)
  texts = lapply(nodes, xml_text)
  
  dt1 = data.table(pmc = articleIds, email = texts)
  dt1 = dt1[, .(email = unlist(email)), by = pmc]
}

url = 'ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/'
pattern = '(?:non_|)comm_use.*\\.xml\\.tar\\.gz'
localDir = 'pmc_files'

fileDT = getAndUnzipRemoteFiles(localDir, url, pattern)




# Once you have all files and folders downloaded, make a data.table of file paths using file.list 

timingsDT = data.table(step = as.character(), elapsed = as.numeric())
con = dbConnect(RPostgres::Postgres(), dbname = 'pmdb', host = 'localhost')
timingsDT = addTimings(timingsDT, 'Start')
dt = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'pmc\' ORDER BY pmid DESC LIMIT 10000;'))
timingsDT = addTimings(timingsDT, 'Query pmc id')
# Uncomment below lines if you want to filter further down the line already existing values.
# dtEmails = setDT(DBI::dbGetQuery(con, 'SELECT email_doi.email, email_doi.doi, article_info.pmid FROM email_doi as email_doi LEFT JOIN article_info as article_info ON email_doi.doi = article_info.doi;'))
# addTimings(timingsDT, 'email query')
# dtEmails = dtEmails[, pmid := as.integer(pmid)]

# FEEDBACK
# Turn certain bits into functions to reduce redundancy
# Have complete accounting of PMC to DOI (maybe another table) then join later to ensure no duplicates. Useful to know all email adress combos.
# Look into iterators package iter function to go by chunks by chunk size. Could also use split function with chunk size and iterate over that.
# Use merge instead of merge.data.table.



chunkSize = 50

numChunks = nrow(dt) %/% chunkSize

timingsDT = addTimings(timingsDT, 'Start loop')

dtNew = foreach(dtTmp = iterators::iter(dt, by = 'row'), .combine = rbind) %do% {
  fileDTFil = fileDT[pmc == dtTmp$id_value,]
  timingsDT = addTimings(timingsDT, paste0('Start xml parse ', i))
  a2 = read_xml(a1)
  # write_xml(a2, paste0(i, 'chunk_', chunkSize, 'chunkSize_entrez.xml'))
  articles = xml_find_all(a2, './/article')
  articleIds = xml_text(xml_find_all(articles, './/article-id[@pub-id-type=\'pmc\']'))
  if (length(articleIds) < length(articles) ) print(i)
  
  dt1 = dtFromXml(articleIds, articles, './/author-notes//email')
  dt2 = dtFromXml(articleIds, articles, './/contrib[@contrib-type=\'author\']//email')
  timingsDT = addTimings(timingsDT, paste0('End xml parse ', i))
  
  timingsDT = addTimings(timingsDT, paste0('End loop chunk ', i))
  rbind(dt1, dt2)
}

timingsDT = addTimings(timingsDT, 'End loop')
dtDOI = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'doi\';'))
timingsDT = addTimings(timingsDT, 'Query doi')

timingsDT = addTimings(timingsDT, 'Start modify data.table')
dtNew[, pmc := paste0('PMC', pmc)]
dtNew = unique(dtNew)
dtNew[, id_value := pmc]
dtMerge = merge.data.table(dtNew, dt, by = 'id_value')
dtMerge = dtMerge[, id_value := NULL]
dtMerge = merge.data.table(dtMerge, dtDOI, by = 'pmid')[, doi := id_value]
# Uncomment below line to add an anti-join to exclude already existing email pairs in DB.
# dtMerge = dtMerge[!dtEmails, on=.(pmid, email)]
# dtMerge = dtMerge[, source := 'pmc_email']
dtMerge = dtMerge[, .(doi, email, pmc)]
timingsDT = addTimings(timingsDT, 'End modify data.table')

timingsDT = addTimings(timingsDT, 'Start insert data.table')
dbExecute(con, 'DELETE FROM pmc_email;')
dbWriteTable(con, 'pmc_email', dtMerge, append = TRUE)
timingsDT = addTimings(timingsDT, 'End insert data.table')

# Uncomment below block to add to email_doi table and reset the doi_child_tables and email_doi_tables indexed tables.
# dbWriteTable(con, 'email_doi', dtMerge, append = TRUE)
# 
# queryDrop1 = 'DROP TABLE IF EXISTS doi_child_tables;'
# queryDrop2 = 'DROP TABLE IF EXISTS email_doi_tables;'
# 
# dbExecute(con, queryDrop1)
# dbExecute(con, queryDrop2)
# 
# queryCreate1 = 'CREATE TABLE doi_child_tables ( \
#                 doi TEXT PRIMARY KEY, \
#                 email_ids INTEGER[], \
#                 author_ids INTEGER[] \
#               );'
# queryCreate2 = 'CREATE TABLE email_doi_tables ( \
#                 email TEXT PRIMARY KEY, \
#                 dois TEXT[] \
#               );'
# 
# dbExecute(con, queryCreate1)
# dbExecute(con, queryCreate2)
# 
# queryInsert1 = 'insert into doi_child_tables(doi, email_ids, author_ids) \
#         	    (select article_info.doi, \
#         	 	  array_remove(array_agg(distinct(email_doi.id)), NULL) as email_ids, \
#         	    array_agg(distinct(author_doi.id)) as author_ids \
#         	    from article_info \
#         	    left join email_doi on article_info.doi = email_doi.doi \
#         	    left join author_doi on article_info.doi = author_doi.doi \
#         	    group by article_info.doi);'
# queryInsert2 = 'insert into email_doi_tables(email, dois) \
#         	    (select email, \
#         	 	  array_agg(doi) as dois \
#         	    from email_doi \
#         	    group by email);'
# 
# dbExecute(con, queryInsert1)
# dbExecute(con, queryInsert2)

timingsDT = addTimings(timingsDT, 'End')
timingsDT[, elapsed := elapsed - timingsDT$elapsed[1]]
timingsDT[, diff := elapsed - shift(elapsed)]

minElapsed = timingsDT$elapsed[nrow(timingsDT)] / 60
print(paste0('Finished, took ', as.character(minElapsed), ' minutes.'))

dbDisconnect(con)


