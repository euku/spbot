"""
The wikis SpBot works on: project id of the archive jobs (-project:<id>) -> database name,
domain and the archive template there.
"""
from collections import namedtuple

Wiki = namedtuple('Wiki', 'project dbname domain template')

WIKIS = [Wiki(*row) for row in (
    ('dewikipedia', 'dewiki', 'de.wikipedia.org', 'Vorlage:Autoarchiv-Erledigt'),
    ('cswikipedia', 'cswiki', 'cs.wikipedia.org', 'Šablona:Archivace vyřešených sekcí'),
    ('itwikipedia', 'itwiki', 'it.wikipedia.org', 'Template:Autoarchivio'),
    ('jawikipedia', 'jawiki', 'ja.wikipedia.org', 'Template:Autoarchive resolved section'),
    ('kowikipedia', 'kowiki', 'ko.wikipedia.org', '틀:완료된 토론 자동 보존'),
    ('viwikipedia', 'viwiki', 'vi.wikipedia.org', 'Bản mẫu:Autoarchive resolved section'),
    ('simplewikipedia', 'simplewiki', 'simple.wikipedia.org', 'Template:Autoarchive resolved section'),
    ('dewiktionary', 'dewiktionary', 'de.wiktionary.org', 'Vorlage:Autoarchiv-Erledigt'),
    ('dewikisource', 'dewikisource', 'de.wikisource.org', 'Vorlage:Autoarchiv-Erledigt'),
    ('enwikisource', 'enwikisource', 'en.wikisource.org', 'Template:Autoarchive resolved section'),
    ('dewikiversity', 'dewikiversity', 'de.wikiversity.org', 'Vorlage:Autoarchiv-Erledigt'),
    ('commons', 'commonswiki', 'commons.wikimedia.org', 'Template:Autoarchive resolved section'),
    ('meta', 'metawiki', 'meta.wikimedia.org', 'Template:Autoarchive resolved section'),
    ('wikidata', 'wikidatawiki', 'www.wikidata.org', 'Template:Autoarchive resolved section'),
    ('wikimania', 'wikimaniawiki', 'wikimania.wikimedia.org', 'Template:Autoarchive resolved section'),
    ('species', 'specieswiki', 'species.wikimedia.org', 'Template:Autoarchive resolved section'),
    ('wikifunctions', 'wikifunctionswiki', 'www.wikifunctions.org', 'Template:Autoarchive resolved section'),
    ('incubator', 'incubatorwiki', 'incubator.wikimedia.org', 'Template:Autoarchive resolved section'),
)]

BY_PROJECT = {wiki.project: wiki for wiki in WIKIS}
