#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from archive_resolved_localization.cs import LocalBotCs
from archive_resolved_localization.de import LocalBotDe
from archive_resolved_localization.en import LocalBotEn
from archive_resolved_localization.ko import LocalBotKo
from archive_resolved_localization.ja import LocalBotJa
from archive_resolved_localization.vi import LocalBotVi

from archive_resolved_localization.meta import LocalBotMeta

"""
    This file extracts all the project and translation related stuff from the main bot code
"""
class LocalBotFactory():
    def createLocalBot(self, projectId: str) -> LocalBot:
        self.projectId = projectId
        projectCode, projectFamily = LocalBot.splitInCodeAndFamily(projectId)
        if projectFamily in LocalBot.multi_lang_projects:
            if projectCode == 'meta':
                return LocalBotMeta(projectId=projectId)
            return LocalBotEn(projectId=projectId)
        
        elif projectCode == 'cs':
            return LocalBotCs(projectId=projectId)
        elif projectCode == 'de':
            return LocalBotDe(projectId=projectId)
        elif projectCode == 'en':
            return LocalBotEn(projectId=projectId)
        elif projectCode == 'ko':
            return LocalBotKo(projectId=projectId)
        elif projectCode == 'ja':
            return LocalBotJa(projectId=projectId)
        elif projectCode == 'vi':
            return LocalBotVi(projectId=projectId)
        
        raise ValueError(f'Unknown project {projectId}')
