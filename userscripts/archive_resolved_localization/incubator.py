#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.en import LocalBotEn

class LocalBotIncubator(LocalBotEn):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        # the rest is inherited from EN
        self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *(?:\w\w/\w{1,3}/)?\ *[Aa]utoarchive\ resolved\ section(?P<options>.*?)\}\}"