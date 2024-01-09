#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.en import LocalBotEn

class LocalBotMeta(LocalBotEn):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        # the rest is inherited from EN
        self.headTemplate   = "{{Archive header}}"
    
    def mustNotArchiveToMainNamespace(self) -> bool:
        """
        Does allow to create an archive in the (Main) namespace!
        """
        return False