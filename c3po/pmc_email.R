library('data.table')
library('rentrez')
library('stringr')
library('xml2')
library('RPostgres')
library('DBI')
library('foreach')
library('doParallel')
library('RCurl')
library('glue')
library('stringr')
options(timeout = 3600)
registerDoParallel()



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

getRemoteFiles = function(localDir, url, pattern) {
  if (!dir.exists(localDir)) {
    dir.create(localDir)
  }
  fNames = getRemoteFilenames(url, pattern)
  fNames[, tar_path := file.path(localDir, tar_filename)]
  setwd(localDir)
  r = foreach(f = iterators::iter(fNames, by = 'row'), .combine = c) %dopar% {
    download(f$download_url, f$tar_filename)
    # untar(f$tar_filename)
  }
  setwd('../')
  # fileDT = data.table(file_paths = list.files(localDir, recursive = TRUE))
  # fileDT[, pmc := str_extract(file_paths, '[ \\w-]+?(?=\\.)')]
  return(fNames)
}

untarFiles = function(fNames, localDir) {
  setwd(localDir)
  r = foreach(f = iterators::iter(fNames, by = 'row'), .combine = c) %dopar% {
    untar(f$tar_filename, exdir = paste0('./', str_replace(f$tar_filename, '.xml.tar.gz', '')))
  }
  setwd('../')
  return(getFilesDT(localDir))
}

getFilesDT = function(localDir) {
  fList = list.files(localDir, recursive = TRUE)
  fileDT = data.table(file_paths = fList)
  fileDT[, pmc := str_extract(file_paths, '[ \\w-]+?(?=\\.nxml)')]
  fileDT = fileDT[!(grepl('comm_use', pmc)),]
  return(fileDT)
}

addTimings = function(timingsDT, stepName) {
  elapsed = proc.time()[['elapsed']]
  timingsDT = rbind(timingsDT, data.table(step = stepName, elapsed = elapsed))
}

dtFromXml = function(articleIds, articles, xpath, entrez = TRUE) {
  # if (isTRUE(entrez)) {
    nodes = xml_find_all(articles, xpath, flatten = FALSE)
    texts = lapply(nodes, xml_text)
    if (length(texts) == 0) return(data.table(pmc = as.character(NA), email = as.character(NA))) 
    
    dt1 = data.table(pmc = articleIds, email = texts)
    if (nrow(dt1) > 0)dt1 = dt1[, .(email = unlist(email)), by = pmc]
    
  # } else {
    
  # }
}

getXmlFromEntrez = function(pmcIds, apiKey) {
  if (is.na(apiKey)) {
    a1 = entrez_fetch(db = 'pmc', id = pmcIds, rettype = 'xml')
  } else {
    a1 = entrez_fetch(db = 'pmc', id = pmcIds, rettype = 'xml', api_key = apiKey)
  }
  return(a1)
}
timingsDT = data.table(step = as.character(), elapsed = as.numeric())
timingsDT = addTimings(timingsDT, 'Start')

url = 'ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/'
pattern = '(?:non_|)comm_use.*\\.xml\\.tar\\.gz'
localDir = 'pmc_files'

filesExist = TRUE
fileDTFilename = file.path(localDir, 'fileDT.csv')

if (isFALSE(filesExist)) {
  timingsDT = addTimings(timingsDT, 'Start download and tar files')
  fNames = getRemoteFiles(localDir, url, pattern)
  fileDT = untarFiles(fNames, localDir)
  timingsDT = addTimings(timingsDT, 'End download and untar files')
} else {
  timingsDT = addTimings(timingsDT, 'Start list files')
  if(is.character(fileDTFilename)) {
    fileDT = fread(fileDTFilename)
  } else {
    fileDT = getFilesDT(localDir)
    fwrite(fileDT, fileDTFilename)
  }
  timingsDT = addTimings(timingsDT, 'End list files')
}

apiKeyFilename = 'c3po/api_key.csv'

apiKey = NA

if (file.exists(apiKeyFilename)) {
  dtAPI = fread(apiKeyFilename)
  apiKey = dtAPI$api_key
}

# Once you have all files and folders downloaded, make a data.table of file paths using file.list 

con = dbConnect(RPostgres::Postgres(), dbname = 'pmdb', host = 'localhost')
timingsDT = addTimings(timingsDT, 'Start query pmc id')
dt = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'pmc\' ORDER BY pmid DESC LIMIT 10000;'))
timingsDT = addTimings(timingsDT, 'End query pmc id')





dt[, hasFile := (id_value %in% fileDT$pmc)]

chunkSize = 50

numChunks = nrow(dt[hasFile == FALSE,]) %/% chunkSize

dtNoFile = dt[hasFile == FALSE,]

dt = merge(dt, fileDT, by.x = 'id_value', by.y = 'pmc')

timingsDT = addTimings(timingsDT, 'Start loop over files')
tick = 0
dtNewFromFiles = foreach(dtTmp = iterators::iter(dt[hasFile == TRUE,], by = 'row'), .combine = rbind) %dopar% {
  tick = tick + 1
  # fileDTFil = fileDT[pmc == dtTmp$id_value,]
  articles = read_xml(file.path(localDir, dtTmp$file_paths))
  articleIds = dtTmp$id_value
  
  dt1 = dtFromXml(articleIds, articles, './/author-notes//email')
  dt2 = dtFromXml(articleIds, articles, './/contrib[@contrib-type=\'author\']//email')
  rbind(dt1, dt2)
}
timingsDT = addTimings(timingsDT, 'End loop over files')

timingsDT = addTimings(timingsDT, 'Start loop over Entrez')
dtNewFromEntrez = foreach(i = 0:(numChunks-1), .combine = rbind) %do% {
  startNum = (i * chunkSize) + 1
  endNum = startNum + chunkSize - 1
  dtTmp = dtNoFile[startNum:endNum,]
  a2 = read_xml(getXmlFromEntrez(dtTmp$id_value, apiKey))
  articles = xml_find_all(a2, './/article')
  articleIds = xml_text(xml_find_all(articles, './/article-id[@pub-id-type=\'pmc\']'))
  if (length(articleIds) < length(articles) ) print(i)
  
  dt1 = dtFromXml(articleIds, articles, './/author-notes//email')
  dt2 = dtFromXml(articleIds, articles, './/contrib[@contrib-type=\'author\']//email')
  
  rbind(dt1, dt2)

}
timingsDT = addTimings(timingsDT, 'End loop over Entrez')

dtNewFromEntrez[, pmc := paste0('PMC', pmc)]
dtNew = rbind(dtNewFromFiles, dtNewFromEntrez)

dtDOI = setDT(DBI::dbGetQuery(con, 'SELECT * FROM article_id WHERE id_type = \'doi\';'))
timingsDT = addTimings(timingsDT, 'Query doi')

timingsDT = addTimings(timingsDT, 'Start modify data.table')
dtNew = unique(dtNew)
dtMerge = merge(dtNew, dt, by.x = 'pmc', by.y = 'id_value', sort = FALSE)
# set(dtMerge, j = 'id_value', value = NULL)
dtMerge = merge(dtMerge, dtDOI, by = 'pmid')[, doi := id_value]

dtMerge = dtMerge[, .(doi, email, pmc)]
timingsDT = addTimings(timingsDT, 'End modify data.table')

timingsDT = addTimings(timingsDT, 'Start insert data.table')
dbExecute(con, 'DELETE FROM pmc_email;')
dbWriteTable(con, 'pmc_email', dtMerge, append = TRUE)
timingsDT = addTimings(timingsDT, 'End insert data.table')

timingsDT = addTimings(timingsDT, 'End')
timingsDT[, elapsed := elapsed - elapsed[1]]
timingsDT[, diff := elapsed - shift(elapsed)]

minElapsed = timingsDT$elapsed[nrow(timingsDT)] / 60
minElapsed = timingsDT[.N]$elapsed / 60
print(paste0('Finished, took ', as.character(minElapsed), ' minutes.'))

dbDisconnect(con)


