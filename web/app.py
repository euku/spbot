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
    return response


@app.after_request
def vary_by_language(response):
    """The pages depend on the browser language and the language cookie."""
    if response.mimetype == 'text/html':
        response.vary.add('Accept-Language')
        response.vary.add('Cookie')
    return response


def _url_without_forced_language():
    """The current path and query string, without the language parameters."""
    args = [(k, v) for k, v in flask.request.args.items(multi=True) if k not in i18n.PARAMS]
    return flask.request.path + ('?' + urlencode(args) if args else '')


@app.context_processor
def inject_globals():
    lang = i18n.current_language()
    here = _url_without_forced_language()
    languages = [(code, flag, name, flask.url_for('set_language', code=code, next=here))
                 for code, (flag, name) in i18n.LANGUAGES.items()]
    return {'_': _, 'lang': lang, 'lang_flag': i18n.LANGUAGES[lang][0], 'lang_name': i18n.LANGUAGES[lang][1],
            'languages': languages, 'now': status.now(), 'github_url': config.github_url,
            'wiki_url': wiki_url, 'tool_url': tool_url}


@app.route('/lang/<code>')
def set_language(code):
    """
    Manual choice in the language menu, then back to the page it came from. The cookie is only
    stored if the choice differs from the browser language (otherwise an old cookie is removed).
    """
    if code not in i18n.LANGUAGES:
        flask.abort(404)
    response = flask.redirect(i18n.local_url(flask.request.args.get('next')))
    if code == i18n.browser_language(flask.request):
        if i18n.COOKIE_NAME in flask.request.cookies:
            response.delete_cookie(i18n.COOKIE_NAME)
    else:
        response.set_cookie(i18n.COOKIE_NAME, code, max_age=i18n.COOKIE_MAX_AGE, httponly=True, samesite='Lax')
    return response


ROBOTS_TXT = (
    'User-agent: *\n'
    'Disallow: /logs/\n'   # log URLs of the old PHP page, no longer served
    'Disallow: /lang/\n'   # sets a cookie and redirects
)


@app.route('/robots.txt')
def robots():
    return flask.Response(ROBOTS_TXT, mimetype='text/plain')


@app.route('/favicon.ico')
def favicon():
    return flask.redirect(flask.url_for('static', filename='favicon.svg'), code=301)


def wiki_url(wiki, title):
    return f'https://{wiki.domain}/wiki/' + quote(title.replace(' ', '_'), safe='/:')


def tool_url(endpoint, **values):
    """url_for that keeps a language given in the URL (uselang/forcedlang)."""
    forced = i18n.forced_language(flask.request)
    if forced:
        values.setdefault(i18n.PARAM, forced)
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


@app.template_filter('pmessage')
def page_message(record):
    """The bot's message about a page: in the chosen language if it has a key, else as recorded."""
    key = record.get('messageKey')
    if key and i18n.has_key('msg.' + key):
        try:
            return _('msg.' + key, **(record.get('messageArgs') or {}))
        except (KeyError, IndexError, ValueError):
            pass
    return record.get('message') or ''


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
