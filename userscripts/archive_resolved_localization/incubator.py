#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.en import LocalBotEn
from archive_resolved_localization.local_bot import OPTIONS_BODY

class LocalBotIncubator(LocalBotEn):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        # the rest is inherited from EN
        # should be able to handle {{CURRENTYEAR}} in the parameter value
        self.optionsRegEx = r"\{\{\ *(?:[Tt]emplate\:)?\ *(?:\w\w/\w{1,3}/)?\ *[Aa]utoarchive\ resolved\ section" + OPTIONS_BODY