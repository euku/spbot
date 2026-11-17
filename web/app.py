"""
Status page of SpBot (https://spbot.toolforge.org/): the services of the bot,
the archive runs per wiki and per page, and the bot account on the wikis.

Runs as Toolforge webservice python3.13 (uwsgi; www/python/src -> bot/web).
"""
import gzip
import re
from urllib.parse import quote, urlencode

import flask
from markupsafe import Markup, escape

import config
import i18n
import status
from i18n import gettext as _
from wikis import BY_PROJECT, WIKIS

app = flask.Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400


@app.after_request
def compress_response(response):
    """Gzips text responses (the archive pages compress about 10 times smaller)."""
    if (response.status_code != 200 or 'Content-Encoding' in response.headers
            or 'gzip' not in flask.request.headers.get('Accept-Encoding', '')
            or response.mimetype not in ('text/html', 'text/css', 'application/json')):
        return response
    response.direct_passthrough = False
    data = response.get_data()
    if len(data) < 1000:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers['Content-Encoding'] = 'gzip'
    response.vary.add('Accept-Encoding')
    if response.mimetype == 'text/html':
        response.vary.add('Accept-Language')
    return response


@app.context_processor
def inject_globals():
    lang = i18n.current_language()
    args = [(k, v) for k, v in flask.request.args.items(multi=True) if k != i18n.PARAM]
    languages = [(code, name, flask.request.path + '?' + urlencode(args + [(i18n.PARAM, code)]))
                 for code, name in i18n.LANGUAGES.items()]
    return {'_': _, 'lang': lang, 'languages': languages, 'now': status.now(), 'github_url': config.github_url,
            'wiki_url': wiki_url, 'tool_url': tool_url, 'config_log_dir': config.log_dir}


def wiki_url(wiki, title):
    return f'https://{wiki.domain}/wiki/' + quote(title.replace(' ', '_'), safe='/:')


def tool_url(endpoint, **values):
    """url_for that keeps the uselang parameter of the current request."""
    if flask.request.args.get(i18n.PARAM) in i18n.LANGUAGES:
        values.setdefault(i18n.PARAM, flask.request.args[i18n.PARAM])
    return flask.url_for(endpoint, **values)


@app.template_filter('dt')
def format_datetime(value, seconds=False):
    if not value:
        return '–'
    if isinstance(value, str):
        value = status.parse_time(value)
    return value.strftime('%Y-%m-%d %H:%M' + (':%S' if seconds else ''))


@app.template_filter('ago')
def format_ago(value):
    """'3 h ago' / 'in 20 min' for a datetime."""
    if not value:
        return ''
    if isinstance(value, str):
        value = status.parse_time(value)
    delta = status.now() - value
    future = delta.total_seconds() < 0
    minutes = abs(int(delta.total_seconds() // 60))
    if minutes < 60:
        text = _('time.minutes', n=minutes)
    elif minutes < 48 * 60:
        text = _('time.hours', n=minutes // 60)
    else:
        text = _('time.days', n=minutes // 1440)
    return _('time.in' if future else 'time.ago', t=text)


@app.template_filter('days')
def format_days(value):
    if value is None:
        return '–'
    return f'{value:.1f}'.replace('.', ',') if i18n.current_language() == 'de' else f'{value:.1f}'


@app.template_filter('reason')
def format_reason(section, page):
    key, values = status.section_reason(page, section)
    values = {k: format_days(v) if isinstance(v, float) else v for k, v in values.items()}
    return _(key, **values)


@app.template_filter('wikilinks')
def wikilinks(text, wiki):
    """[[Title]] in messages -> links to the wiki."""
    text = str(escape(text or ''))
    if wiki is None:
        return Markup(text)
    return Markup(re.sub(r'\[\[([^\[\]|]+)\]\]',
                         lambda m: f'<a href="{wiki_url(wiki, Markup(m.group(1)).unescape())}">{m.group(1)}</a>', text))


@app.route('/')
def index():
    jobs = status.read_jobs()
    archive = status.archive_overview(jobs)
    return flask.render_template('index.html', archive=archive,
                                 archive_state=status.worst(row['state'] for row in archive),
                                 services=status.services(jobs), accounts=status.bot_accounts(),
                                 software=status.software())


@app.route('/archive')
def archive():
    project = flask.request.args.get('project', '').strip()
    title = status.normalize_title(flask.request.args.get('page', ''))
    if project and project not in BY_PROJECT:
        flask.abort(404)
    if project and title:
        return archive_page(project, title)
    if project:
        return archive_project(project)
    jobs = status.read_jobs()
    return flask.render_template('archive.html', rows=status.archive_overview(jobs), wikis=WIKIS)


def archive_project(project):
    wiki = BY_PROJECT[project]
    row = next(iter(status.archive_overview(only=project)), None)
    run = row['run'] if row else None
    pages = sorted(run['pages'].values(), key=lambda r: r['title']) if run else []
    query = flask.request.args.get('q', '').strip()
    matches = status.find_pages(project, query, limit=200) if query else None
    return flask.render_template('archive_project.html', wiki=wiki, row=row, run=run, query=query, matches=matches,
                                 problems=[p for p in pages if p['status'] in ('skipped', 'optionserror', 'error')],
                                 archived=[p for p in pages if p['status'] in ('archived', 'dryrun')], wikis=WIKIS)


def archive_page(project, title):
    wiki = BY_PROJECT[project]
    run, record = status.page_record(project, title)
    if record is None:
        matches = status.find_pages(project, title)
        if len(matches) == 1:
            return flask.redirect(tool_url('archive', project=project, page=matches[0]))
        return flask.render_template('archive_page.html', wiki=wiki, run=run, title=title, record=None,
                                     matches=matches, history=[], wikis=WIKIS), 404
    return flask.render_template('archive_page.html', wiki=wiki, run=run, title=record['title'], record=record,
                                 matches=None, history=status.page_history(project, record['title']), wikis=WIKIS)


@app.route('/healthz')
def healthz():
    return 'ok'
