# Notes

## How to run

1. Copy `cloud-flare.sh` to `cloud-flare.local.sh` and fill in your Cloudflare
   account ID and an API token with Workers AI Read + Edit permissions.
   (`cloud-flare.local.sh` is git-ignored, so the token never gets committed.)
2. Run the two passes (Python 3, standard library only - no installs):

   ```
   python3 classify.py --input comments.json    --html comments.html    --json classifications.json    --model clef-flash
   python3 classify.py --input comments-v2.json --html results-v2.html  --json classifications-v2.json --model clef
   ```

3. Open the HTML files in a browser. Toxic/spam rows and low-confidence
   classifications float to the top so mistakes are easy to scan for.

## Tools and models used

- Cloudflare Workers AI decision models: `clef-flash` for `comments.json` and
  the larger `clef` for `comments-v2.json`, called over the REST API.
- AI assistant (Instinct) to write and check `classify.py` and the HTML report,
  as steps 1-5 allow.
- The Clef `instructions` and `criteria` in `classify.py` describe what counts
  as acceptable, toxic, and spam for this course forum; the wording matters a
  lot for how many mistakes Clef makes.

## My own review (steps 6 and 7, done by hand)

- I reviewed all 200 comments against Clef's labels myself. `MISTAKES.md` and
  `MISTAKES-v2.md` record where I disagreed: none in the first set, two in the
  harder set.
- Reflection on the task: [to be written by me]
