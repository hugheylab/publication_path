INSERT INTO email_doi(email, doi, source) 
    (SELECT DISTINCT email, doi, 'pmc' as source
    FROM pmc_email
    WHERE NOT EXISTS (
        SELECT 'X' 
        FROM email_doi
        WHERE 
            email_doi.email = pmc_email.email
            AND email_doi.doi = pmc_email.doi
));
DELETE FROM doi_child_tables;
DELETE FROM email_doi_tables;
INSERT INTO doi_child_tables(doi, email_ids, author_ids) 
	(SELECT article_info.doi, 
	ARRAY_REMOVE(ARRAY_AGG(DISTINCT(email_doi.id)), NULL) AS email_ids, 
	ARRAY_AGG(DISTINCT(author_doi.id)) AS author_ids 
	FROM article_info 
	LEFT JOIN email_doi ON article_info.doi = email_doi.doi 
	LEFT JOIN author_doi ON article_info.doi = author_doi.doi 
	GROUP BY article_info.doi
);
INSERT INTO email_doi_tables(email, dois) 
	(SELECT email, 
	ARRAY_AGG(doi) AS dois 
	FROM email_doi 
	GROUP BY email
);