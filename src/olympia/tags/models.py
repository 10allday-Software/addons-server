from django.db import models
from django.urls import NoReverseMatch, reverse

from olympia import activity, amo
from olympia.amo.fields import PositiveAutoField
from olympia.amo.models import ModelBase


class Tag(ModelBase):
    id = PositiveAutoField(primary_key=True)
    tag_text = models.CharField(max_length=128)
    addons = models.ManyToManyField(
        'addons.Addon', through='AddonTag', related_name='tags'
    )
    num_addons = models.IntegerField(default=0)

    class Meta:
        db_table = 'tags'
        ordering = ('tag_text',)
        constraints = [models.UniqueConstraint(fields=('tag_text',), name='tag_text')]

    def __str__(self):
        return self.tag_text

    @property
    def popularity(self):
        return self.num_addons

    def can_reverse(self):
        try:
            self.get_url_path()
            return True
        except NoReverseMatch:
            return False

    def get_url_path(self):
        return reverse('tags.detail', args=[self.tag_text])

    def add_tag(self, addon):
        AddonTag.objects.get_or_create(addon=addon, tag=self)
        activity.log_create(amo.LOG.ADD_TAG, self, addon)

    def remove_tag(self, addon):
        for addon_tag in AddonTag.objects.filter(addon=addon, tag=self):
            addon_tag.delete()
        activity.log_create(amo.LOG.REMOVE_TAG, self, addon)

    def update_stat(self):
        self.num_addons = self.addons.count()
        self.save()


class AddonTag(ModelBase):
    id = PositiveAutoField(primary_key=True)
    addon = models.ForeignKey(
        'addons.Addon', related_name='addon_tags', on_delete=models.CASCADE
    )
    tag = models.ForeignKey(Tag, related_name='addon_tags', on_delete=models.CASCADE)

    class Meta:
        db_table = 'users_tags_addons'
        indexes = [
            models.Index(fields=('tag',), name='tag_id'),
            models.Index(fields=('addon',), name='addon_id'),
        ]
        constraints = [
            models.UniqueConstraint(fields=('tag', 'addon'), name='tag_id_2'),
        ]


def update_tag_stat_signal(sender, instance, **kw):
    from .tasks import update_tag_stat

    if not kw.get('raw'):
        try:
            update_tag_stat.delay(instance.tag.pk)
        except Tag.DoesNotExist:
            pass


models.signals.post_save.connect(
    update_tag_stat_signal, sender=AddonTag, dispatch_uid='update_tag_stat'
)
models.signals.post_delete.connect(
    update_tag_stat_signal, sender=AddonTag, dispatch_uid='delete_tag_stat'
)
