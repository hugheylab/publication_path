cd pmc_output
wget https://www.dropbox.com/s/53febkxfinckfkk/pmc_email.csv?dl=1
mv 'pmc_email.csv?dl=1' pmc_email.csv
psql pmdb -q "DELETE FROM pmc_email;"
psql pmdb -q "COPY pmc_email(doi, email, pmc) 
FROM '/home/ubuntu/pmc_output/pmc_email.csv' 
DELIMITER ','
CSV HEADER;"
cd ../
psql pmdb -f c3po/pmc_email_add.sql
