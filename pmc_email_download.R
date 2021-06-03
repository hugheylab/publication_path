library('data.table')
library('DBI')
library('foreach')
library('rdrop2')
options(timeout = 3600)
token = readRDS('tokens/token.rds')

#Connect to DB
connectDB = function() {
  return(dbConnect(RPostgres::Postgres(), dbname = 'pmdb', host = 'localhost', password = 'password'))}

localDir = 'pmc_files'
dropPath = 'Publication Path Files'
fileNames = setDT(drop_dir(path = dropPath, dtoken = token))[.tag == 'file',]$name
delFromTable = TRUE
if (isTRUE(delFromTable)) {
  con = connectDB()
  
  dbExecute(con, 'DELETE FROM pmc_email;')
  
  dbDisconnect(con)
}
#Try downloading then lapply to get data.table
for (fileName in fileNames) {
  localPath = file.path(localDir, fileName)
  drop_download(file.path(dropPath, fileName), localPath, dtoken = token, overwrite = TRUE)
  pmcDT = fread(localPath)
  
  con = connectDB()
  
  dbWriteTable(con, 'pmc_email', pmcDT, append = TRUE)
  
  dbDisconnect(con)
}


