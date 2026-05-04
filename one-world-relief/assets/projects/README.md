# Project Media

Put project photos, thumbnails, and short clips here when you want the site to use local files instead of hosted links.

Recommended structure:

```text
assets/projects/
  wells/
    village-well-thumbnail.jpg
    village-well-complete-01.jpg
  feeding/
    feeding-campaign-thumbnail.jpg
  orphans/
    orphan-support-thumbnail.jpg
```

Keep images compressed before adding them to Git. A good target is under 500 KB per image for thumbnails and under 1.5 MB for larger project photos.

For videos, the easiest option is usually to upload the video to YouTube as unlisted, then paste the YouTube link into `project-data.js` as `mediaUrl`.
