#!/usr/bin/env bash
# Download the official source documents into kb/raw/ (git-ignored) and verify them against the sha256 recorded in
# kb/sources.md on 2026-11-08. Run on a machine with normal internet access:  bash scripts/fetch_sources.sh
set -u
cd "$(dirname "$0")/.."
mkdir -p kb/raw
UA="Mozilla/5.0 (research; itu-alert-governance KB build)"
ok=0; bad=0; miss=0
fetch() {  # doc_id  url  expected_sha256 (or "pending")  extension
  local id=$1 url=$2 want=$3 ext=$4 out="kb/raw/$1.$4"
  # Sites that block scripts (403) need a manual browser save; never let a failed download touch such a file.
  if ! curl -sSL -A "$UA" --fail -o "$out.part" "$url"; then
    rm -f "$out.part"
    if [ ! -s "$out" ]; then echo "MISSING  $id  ($url)"; miss=$((miss+1)); return; fi
    echo "         $id: download blocked, verifying the manually saved file"
  else mv "$out.part" "$out"; fi
  local got; got=$(shasum -a 256 "$out" 2>/dev/null | cut -d' ' -f1 || sha256sum "$out" | cut -d' ' -f1)
  if [ "$want" = "pending" ]; then echo "NEW      $id  sha256=$got  (record this in kb/sources.md)"; ok=$((ok+1))
  elif [ "$want" = "volatile" ]; then echo "FETCHED  $id  (whole-file hash not meaningful; see article-level check)"; ok=$((ok+1))
  elif [ "$got" = "$want" ]; then echo "OK       $id"; ok=$((ok+1))
  else echo "CHANGED  $id  got=$got  want=$want  (publisher changed the file; review before ingesting)"; bad=$((bad+1)); fi
}
fetch ae-dl-2-2011-ncema      "https://uaelegislation.gov.ae/ar/legislations/4461/download" 3078bca67808d107c8470121b9a280b088ea00621183dcb69fb8d022b2f6735c pdf
fetch ae-dl-8-2025-faacd      "https://uaelegislation.gov.ae/en/legislations/3231/download" f552b3dee96488e5838aead243920ae72303585ec5ef054ffacbe0c9d5d22e4b pdf
fetch ae-dl-35-2024-cda       "https://uaelegislation.gov.ae/en/legislations/2771/download" 73a75bfec06bcf60995a9572f405e03e3e8ee021d7f9f01e0efe62b27c75dc21 pdf
fetch ae-dl-3-2003-telecom    "https://uaelegislation.gov.ae/en/legislations/1132/download" ad162193811d06fc224cc9997abd7bafc3ebcc20a53df1e45708b34172aa1bab pdf
fetch ae-tdra-uae-alert-table "https://tdra.gov.ae/userfiles/assets/lgz6mOeOihm.pdf"         4e2fdc285cb5d34818c0208862584cf30854e968a8fbf3d404f8613bf25f3eec pdf
fetch ae-tdra-licence-3-2026  "https://tdra.gov.ae/-/media/About/LICENSING/EN/Licence-32026-EITC-Public.ashx" ccafd4ed2d5a960bc1fb2ff27c6161a95a948ee2547ac13b87589a79ddcf7924 pdf
fetch ae-tdra-ts-fs-001       "https://tdra.gov.ae/-/media/About/Type-Approval/Technical-Standards-2021/TS-FS-001-Emergency-Broadcast.ashx" a5776742439647dcd8f48e12ab968c501162c686b67b331ce1a9473f22e3c737 pdf
fetch ae-dl-45-2021-pdpl     "https://uaelegislation.gov.ae/en/legislations/1972/download" d5d5f9e93bd6c0dc2afe79776f3101bcd599e4400a67309bc0b378b2812bcf3a pdf
fetch ae-dl-34-2021-rumours   "https://uaelegislation.gov.ae/en/legislations/1526/download" f438fdf264b93c9d108ff4d40633aa55e798e63f47a951943a372ea73ee938e1 pdf
fetch ae-ai-strategy-2031     "https://u.ae/-/media/AI-publications/UAE-National-Strategy-for-Artificial-Intelligence-2031.pdf" pending pdf
fetch us-fcc-hawaii-2018      "https://docs.fcc.gov/public/attachments/DOC-350119A1.pdf" d19c432a20ac86e14165221aa906d780c97c87489afabc23a6b61a04d48235c0 pdf
fetch us-fcc-hawaii-2018-txt  "https://docs.fcc.gov/public/attachments/DOC-350119A1.txt" c1d4f96806c98226f8ebadfe56ddb4487edb7a2d2b0ec22f9f6b7d4e0d93e509 txt
# EUR-Lex HTML differs byte-for-byte on every fetch (dynamic page elements; two fetches on 2026-11-08 gave different
# hashes), so a whole-file hash is meaningless. We pin the extracted text of Article 110 instead.
fetch eu-eecc-2018-1972       "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32018L1972" volatile html
if [ -f kb/raw/eu-eecc-2018-1972.html ]; then
  python3 -I - <<'PY'
import re, html, hashlib
WANT = "a0575a7546a097041cce53f2542a3410d820dc29a20f42beb28caf14b332a442"  # sha256 of Art. 110 text, recorded 2026-11-08
t = open("kb/raw/eu-eecc-2018-1972.html", encoding="utf-8", errors="replace").read()
s = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))
i = s.find("Article 110 Public warning system"); j = s.find("Article 111", i)
got = hashlib.sha256(s[i:j].strip().encode()).hexdigest() if i >= 0 and j > i else "ARTICLE NOT FOUND"
print("OK       eu-eecc-2018-1972 (Art. 110 text hash)" if got == WANT else f"CHANGED  eu-eecc-2018-1972 Art. 110 text  got={got}  want={WANT}")
PY
fi
fetch itu-x1303bis-cap        "https://www.itu.int/en/ITU-D/Emergency-Telecommunications/Documents/2020/T-REC-X.1303bis-201403-.pdf" 79ec13413942e8e36526ddd38b4ce6d9a9f3197f106d07277e239b255fd45114 pdf
fetch itu-ew4all-arab-cb-2026 "https://www.itu.int/en/ITU-D/Emergency-Telecommunications/Documents/2026/EW4All/Arab%20States_CB_Partner%20Brief_Oct%202026.pdf" 01906532c98571bec2c75b6a76ff365655cc05f46da54ca9600e755d0162dc51 pdf
fetch itu-y3172-2019           "https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-Y.3172-201906-I!!PDF-E&type=items" e42f9a3be3f951d3e19b9007f876f0b389c81b4693f0d8576e18185a1acfe67b pdf
fetch itu-ai-ready-2-0         "https://www.itu.int/dms_pub/itu-t/opb/ai4g/T-AI4G-AI4GOOD-2025-6-PDF-E.pdf" 71191768d46b60778c15f8d62b162aff73a319785cfc31ebf76bb944b0c68273 pdf
echo; echo "verified=$ok changed=$bad missing=$miss"
# Some sites (FCC, EUR-Lex) use bot protection; if a file is MISSING, open the URL in a browser, save it as
# kb/raw/<doc_id>.<ext>, and re-run this script to verify the hash.
