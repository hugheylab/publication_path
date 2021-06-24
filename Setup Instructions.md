# Setup Instructions

## Setting up C3PO

1. Download and initialize the PMDB database (available here with instructions: [https://zenodo.org/record/4584101#.YNIaM5NKi7N](https://zenodo.org/record/4584101#.YNIaM5NKi7N))
2. Once initialized, clone the `publication_path` repository from here: [https://github.com/hugheylab/publication_path](https://github.com/hugheylab/publication_path) you will also need to add 2 files of your own:
    1. `c3po/database.ini` - This file is a formatted database authorization file to use when connecting to your pmdb instance. Here is an example:

        ```bash
        [postgresql]
        host=localhost
        database=pmdb
        user=username
        password=password
        ```

    2. `tokens/token.rds` - This is a dropbox authorization file that needs to be generated using the authentication steps here [https://github.com/karthik/rdrop2#authentication](https://github.com/karthik/rdrop2#authentication). NOTE: I have had trouble getting this to work in remote servers such as EC2, so you can do this locally then upload the file using `rsync` or some other file transfer method!
3. Create a new tmux session.
4. In the newly created tmux session, set your working directory to the publication_path repository directory.
5. Install required python libraries by running `pip install -r requirements.txt`
6. Once the requirements are met, set up a virtual environment by running `python3 -m venv venv`
7. Then, you can activate the virtual environment and set everything up to host the site on port 5000 using the commands in the `setup.sh` file:

    ```bash
    . venv/bin/activate
    export FLASK_APP="c3po"
    export FLASK_ENV="development"
    flask init-db-postgres
    flask run -h 0.0.0.0 -p 5000
    ```

8. The above steps do the following (in order):
    1. Activate the virtual environment.
    2. Set the FLASK_APP variable to "c3po"
    3. Set the FLASK_ENV variable as development
    4. Initialize the database using the flask command.
    5. Set up and host the web application.
9. At this point, the app is running! It is only using information provided from pmdb however.

## Extract emails from pmc and add to host site

1. This process can only be done once you have done all steps up to and including 8.4 (running `flask init-db-postgres` command) on the site hosting the site.
2. Set up a separate EC2 instance (or run locally, but be aware this process takes a lot of time). From here on out, we will refer to the server hosting the site as "H1" and the newly initialized server for pmc parsing as "H2."
3. On H2, you will need to repeat steps 1-2 from "Setting up C3PO" so there is an instance of pmdb, you have cloned the repository, and you have a `token.rds` file present to use when uploading to dropbox.
    1. You don't need the `c3po/database.ini` file on H2.
    2. It's not required to have a pmc api key, but you will probably run into many issues if you don't have one. You should store it as a single row csv with the api key stored in a column titled `api_key` . The default file location used to check is `c3po/api_key.csv` .
    3. Another thing you should have is a folder in your dropbox for uploading these files to. By default, it is set to a folder on your main dropbox directory titled `Publication Path Files`
4. While not necessary, I would highly suggest using RStudio or some other sort of editor to go have handy so you can make adjustments to the code prior to processing and have a neat visual representation of what all happened. RStudio Server is great for this and only requires that you expose port `8787` for use to log in using a browser. See here to download: [https://www.rstudio.com/products/rstudio/download-server/](https://www.rstudio.com/products/rstudio/download-server/) and here to get started: [https://support.rstudio.com/hc/en-us/articles/200552306-Getting-Started](https://support.rstudio.com/hc/en-us/articles/200552306-Getting-Started) 
5. `pmc_email.R` is the script you will be using to parse pmc for any email addresses. The way it currently works is as such:
    1. Parses the filenames of the PMC Open Access bulk files from the ftp site.
    2. Downloads the bulk files using the filenames parsed.
    3. Get the pmc api key from the file if present.
    4. Get a list of all pmc IDs that need to be checked for in the files vs. using the pmc api.
    5. Iterate over all pmc IDs with a file and parse out any emails found.
    6. Iterate over all pmc IDs that do not have a file and use the API to query for them, then parse any emails found.
    7. Break up the data into several chunks to save as separate csv files. This is done because rdrop2 has an upload size limit we want to avoid.
    8. Upload the csv files to dropbox using rdrop2.
6. You will probably need to make adjustments in the `pmc_email.R` script for this to run how you want. I will highlight some variables and functions that will be the most relevant here:
    1. `token` Line 15: This is the dropbox token object saved as an rds file to be used.
    2. `connectDB()` Lines 20-21: Here I just have a basic method that automatically connects to a database and returns a connection object. You might need to change the `dbname`, `host`, and/or `password` arguments as necessary to connect to your pmdb instance.
    3. `localDir` Line 120: This is the local directory on H2 that will be used to download all of the files then parse through. It is also where the output will be saved at the end.
    4. `filesExist` Line 122: This is the boolean to determine if files have already been downloaded. If set to `TRUE` it will skip downloading the files from pmc and try to parse what already exists.
    5. `apiKeyFilename` Line 141: This is the path to your api_key file for use with the pmc API.
    6. `fresh` Line 152 IMPORTANT: This variable determines if this is a fresh run of parsing pmc (as in, the first one and it needs to set or clean up everything in the DB) or not. If it is set to `TRUE` the relevant tables used will be dropped and recreated, then it will parse and check every pmc ID found in pmdb. If set to `FALSE` , it will limit the amount of pmc IDs parsed by checking the local database for already parsed IDs to exclude from this run.
    7. `chunkSize` Line 171: This variable determines how many pmc IDs to query the API for, since there are limits to the amount of data that can be returned. `50` is the default, and has been safe thus far without breaking any limits. Feel free to adjust if you wish to see if it will run faster in larger chunks and less API calls.
    8. `writeChunkSize1` Line 240: This variable determines the amount of rows written to each csv being uploaded to dropbox to avoid the file size limit. As above with `chunkSize`, the default has been safe thus far but feel free to adjust, especially if they ever expand the file size limit.
    9. `drop_upload()` Line 248: Specifically, the `path` argument. This is the path in your dropbox directory that the files will be uploaded to. By default it is set to `Publication Path Files` , but you may change it to whatever folder you wish, so long as it exists on your dropbox prior to calling the upload.
7. Once adjustments have been made and you are comfortable with the environment you have everything in in H2, You can run the whole script file (on H2) using the following command:
    ```bash
    Rscript pmc_email.R
    ```
8. To see if there were any pmc IDs that failed for any reason, simply query the `pmc_parse_status` table on the database and compare that against the `dtAll` variable set on line 156. `pmc_parse_status` will show all pmc IDs (including those where no emails were found) that have been parsed.
9. If you need to run again due to errors while processing, pmdb has been updated with new pmc IDs, or whatever reason, you can simply run the entire script again! To save time, it is highly recommended you set the `fresh` variable from step 6.6 to `FALSE` for incremental updates/ error handling.
10. Once you have completed steps 1-9 and repeated as necessary, you can now use the `pmc_email_download.R` script on H1 to download the files from dropbox and insert into the DB for use with the site.
11. `pmc_email_download.R` works generally as such:
    1. Get the filenames of each chunk from dropbox.
    2. Download the files from dropbox.
    3. Insert the data from the files into an intermediary table.
12. Again, you may have to modify some of the variables, so see some of those below:
    1. `token` Line 6: See 6.1.
    2. `connectDB()` Lines 9-10: See 6.2.
    3. `localDir` Line 12: See 6.3.
    4. `dropPath` Line 13: This is used to supply the `path` argument to the dropbox calls. See 6.9 for more information.
    5. `delFromTable` Line 15: This deletes all data from the `pmc_email` table on H1. Useful to reduce processing time by having potential duplicates, but not recommended to use if you are incrementally adding items.
13. Once you have modified the script as necessary, you can run the script using the following command:
    ```bash
    Rscript pmc_email_download.R
    ```
14. The final step is to run the `pmc_email_add.sql` script to insert the data into pmdb and reformat/update all reference IDs.
15. Before using the `pmc_email_add.sql` script, be aware that this will partially re-initialize the database. Because of that, **the site will need to be down for a while as the script runs**. Leaving the site up not only diverts away processing power from the sql script running, it also will not have any emails on file until the final step completes. This last step can take about 30 minutes to 2 hours.
16. Once you have modified the script as necessary and are aware of the implications highlighted in step 14, you can run the script using the following command:
    ```bash
    psql pmdb -f c3po/pmc_email_add.sql
    ```
17. If you wish to minimize site downtime as much as possible, I would recommend running the whole script except for the final line. Then, once that execution has finished, take down the site and run the final line. Once that final step has fully finished, bring the site back up!
