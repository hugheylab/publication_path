library('data.table')
library('rentrez')
library('stringr')
library('xml2')

# get PMCID from pmdb

##########
# simpler for some papers, but email address(es) cannot be linked to author names

pmcid = 'PMC7815206'
# pmcid = 'PMC7046182'
# pmcid = 'PMC6857501'

a1 = entrez_fetch(db = 'pmc', id = pmcid, rettype = 'xml')
write(a1, file.choose(new = TRUE))
a2 = read_xml(a1)
# xml_text(xml_find_first(a2, './/author-notes'))
a3 = xml_text(xml_find_all(xml_find_first(a2, './/author-notes'), './/email'))
d = data.table(pmcid = pmcid,
               email = a3)
d = d[!is.na(email)]

##########
# more complicated for some papers, but email address(es) can be linked to author names

# pmcid = 'PMC6914335'
pmcid = 'PMC6535214'

a1 = entrez_fetch(db = 'pmc', id = pmcid, rettype = 'xml')
a2 = read_xml(a1)
a3 = xml_find_all(a2, './/contrib')
d = data.table(pmcid = pmcid,
               contrib_type = xml_attr(a3, 'contrib-type'),
               surname = xml_text(xml_find_first(a3, './/surname')),
               given_name = xml_text(xml_find_first(a3, './/given-names')),
               email = xml_text(xml_find_first(a3, './/email')))
d = d[contrib_type == 'author' & !is.na(email)]
d[, contrib_type := NULL]

