from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .assistant import clear_public_corpus_cache
from .models import (
    Announcement,
    Answer,
    Article,
    CompetitionCalendarEvent,
    CompetitionNotice,
    CompetitionPracticeLink,
    CompetitionScheduleEntry,
    CompetitionZoneSection,
    ExtensionPage,
    FriendlyLink,
    Question,
    TrickEntry,
)

@receiver(post_save, sender=Announcement)
@receiver(post_save, sender=Answer)
@receiver(post_save, sender=Article)
@receiver(post_save, sender=CompetitionCalendarEvent)
@receiver(post_save, sender=CompetitionNotice)
@receiver(post_save, sender=CompetitionPracticeLink)
@receiver(post_save, sender=CompetitionScheduleEntry)
@receiver(post_save, sender=CompetitionZoneSection)
@receiver(post_save, sender=ExtensionPage)
@receiver(post_save, sender=FriendlyLink)
@receiver(post_save, sender=Question)
@receiver(post_save, sender=TrickEntry)
@receiver(post_delete, sender=Announcement)
@receiver(post_delete, sender=Answer)
@receiver(post_delete, sender=Article)
@receiver(post_delete, sender=CompetitionCalendarEvent)
@receiver(post_delete, sender=CompetitionNotice)
@receiver(post_delete, sender=CompetitionPracticeLink)
@receiver(post_delete, sender=CompetitionScheduleEntry)
@receiver(post_delete, sender=CompetitionZoneSection)
@receiver(post_delete, sender=ExtensionPage)
@receiver(post_delete, sender=FriendlyLink)
@receiver(post_delete, sender=Question)
@receiver(post_delete, sender=TrickEntry)
def invalidate_public_corpus(**kwargs):
    clear_public_corpus_cache()


@receiver(m2m_changed, sender=TrickEntry.terms.through)
def invalidate_public_corpus_for_trick_terms(**kwargs):
    clear_public_corpus_cache()
