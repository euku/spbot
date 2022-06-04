Current release 7.3.0
^^^^^^^^^^^^^^^^^^^^^

* Add support for kcgwiki (:phab:`T305282`)
* Raise InvalidTitleError instead of unspecific ValueError in ProofreadPage (:phab:`T308016`)
* Preload pages if GeneratorFactory.articlenotfilter_list is not empty; also set attribute ``is_preloading``.
* ClaimCollection.toJSON() should not ignore new claim (:phab:`T308245`)
* use linktrail via siteinfo and remove `update_linkrtrails` maintenance script
* Print counter statistic for all counters (:phab:`T307834`)
* Use proofreadpagesinindex query module
* Prioritize -namespaces options in `pagegenerators.handle_args` (:phab:`T222519`)
* Remove `ThreadList.stop_all()` method (:phab:`T307830`)
* L10N updates
* Improve get_charset_from_content_type function (:phab:`T307760`)
* A tiny cache wrapper was added to hold results of parameterless methods and properties
* Increase workers in preload_sites.py
* Close logging handlers before deleting them (:phab:`T91375`, :phab:`T286127`)
* Clear _sites cache if called with pwb wrapper (:phab:`T225594`)
* Enable short creation of a site if family name is equal to site code
* Use `exc_info=True` with pywikibot.exception() by default (:phab:`T306762`)
* Make IndexPage more robust when getting links in Page ns (:phab:`T307280`)
* Do not print log header twice in log files (:phab:`T264235`)
* Do not delegate logging output to the root logger (:phab:`T281643`)
* Add `get_charset_from_content_type` to extract the charset from the content-type response header


Deprecations
^^^^^^^^^^^^

* 7.3.0: Python 3.5 support will be dropped with Python 8 (:phab:`T301908`)
* 7.2.0: XMLDumpOldPageGenerator is deprecated in favour of a `content` parameter (:phab:`T306134`)
* 7.2.0: RedirectPageBot and NoRedirectPageBot bot classes are deprecated in favour of `use_redirects` attribute
* 7.2.0: `tools.formatter.color_format` is deprecated and will be removed
* 7.1.0: win32_unicode.py will be removed with Pywikibot 8
* 7.1.0: Unused `get_redirect` parameter of Page.getOldVersion() will be removed
* 7.1.0: APISite._simple_request() will be removed in favour of APISite.simple_request()
* 7.0.0: The i18n identifier 'cosmetic_changes-append' will be removed in favour of 'pywikibot-cosmetic-changes'
* 7.0.0: User.isBlocked() method is renamed to is_blocked for consistency
* 7.0.0: Require mysql >= 0.7.11 (:phab:`T216741`)
* 7.0.0: Private BaseBot counters _treat_counter, _save_counter, _skip_counter will be removed in favour of collections.Counter counter attribute
* 7.0.0: A boolean watch parameter in Page.save() is deprecated and will be desupported
* 7.0.0: baserevid parameter of editSource(), editQualifier(), removeClaims(), removeSources(), remove_qualifiers() DataSite methods will be removed
* 7.0.0: Values of APISite.allpages() parameter filterredir other than True, False and None are deprecated
* 6.5.0: OutputOption.output() method will be removed in favour of OutputOption.out property
* 6.5.0: Infinite rotating file handler with logfilecount of -1 is deprecated
* 6.4.0: 'allow_duplicates' parameter of tools.intersect_generators as positional argument is deprecated, use keyword argument instead
* 6.4.0: 'iterables' of tools.intersect_generators given as a list or tuple is deprecated, either use consecutive iterables or use '*' to unpack
* 6.2.0: outputter of OutputProxyOption without out property is deprecated
* 6.2.0: ContextOption.output_range() and HighlightContextOption.output_range() are deprecated
* 6.2.0: Error messages with '%' style is deprecated in favour for str.format() style
* 6.2.0: page.url2unicode() function is deprecated in favour of tools.chars.url2string()
* 6.2.0: Throttle.multiplydelay attribute is deprecated
* 6.2.0: SequenceOutputter.format_list() is deprecated in favour of 'out' property
* 6.0.0: config.register_family_file() is deprecated
* 5.5.0: APISite.redirectRegex() is deprecated in favour of APISite.redirect_regex() and will be removed with Pywikibot 8
* 4.0.0: Revision.parent_id is deprecated in favour of Revision.parentid and will be removed with Pywikibot 8
* 4.0.0: Revision.content_model is deprecated in favour of Revision.contentmodel and will be removed with Pywikibot 8
