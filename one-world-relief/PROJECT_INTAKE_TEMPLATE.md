# One World Relief Project Intake Template

Use this when you want to add a new completed project or active campaign to the Projects page.

## Basic Info
- Project title:
- Category: Wells / Orphan Support / Feeding / Zakat / Emergency Relief / Other
- Status: Completed / Active / Urgent Need
- Location:
- Date or timeline:
- Amount raised:
- What donations paid for:

## Donor-Facing Summary
Write 2-3 sentences explaining what happened, who benefited, and why it matters.

## Latest Update
Write one short update donors can read quickly. Example:

`Food packs were delivered to 40 families in April 2026. Photos and receipts are available for donor review.`

## Photos
Send:
- 1 main thumbnail photo for the project card
- 3-8 supporting photos if available
- Any receipt/proof photos that are safe to show publicly

Photo tips:
- Use JPG or PNG.
- Avoid showing private personal information.
- Rename files clearly, like `gaza-feeding-april-2026-01.jpg`.

## Videos
Best option:
- Upload the video to YouTube as unlisted.
- Send the YouTube link.

Alternative:
- Put MP4 files in `one-world-relief/assets/projects/...`, but keep files small so GitLab does not get too heavy.

## Data Entry
Each project becomes one object in `project-data.js` with:

```js
{
  title: "Project Name",
  category: "Wells",
  status: "Completed",
  location: "Location",
  date: "Completed 2026",
  amountRaised: "$0",
  impact: "Short impact line",
  summary: "Two sentence donor-facing summary.",
  update: "Latest project update.",
  thumbnailUrl: "assets/projects/example/example-thumbnail.jpg",
  mediaLabel: "View project media",
  mediaUrl: "https://www.youtube.com/",
  donationUrl: "donate.html?campaign=Wells#donationForm"
}
```
