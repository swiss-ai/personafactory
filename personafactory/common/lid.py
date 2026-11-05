"""Language identification used throughout the pipeline and the release build.

fastText lid.176 (download: https://fasttext.cc/docs/en/language-identification.html) at p >= 0.5 with a
Lingua fallback. Language names are normalized to one canonical name per language; Malay/Indonesian and
Bokmal/Norwegian are merged because the detector cannot separate them.
"""
import os, re, sys

ALIASES = {
 'mandarin':'Chinese','mandarin chinese':'Chinese','filipino':'Tagalog','bangla':'Bengali',
 'bangladesh':'Bengali','bahasa indonesia':'Indonesian','bahasa indonesian':'Indonesian',
 'bahasa malaysia':'Malay','bahasa melayu':'Malay','slovene':'Slovenian','slovenčina':'Slovak',
 'farsi':'Persian','burma':'Burmese','myanmar':'Burmese','bamar':'Burmese','burmes':'Burmese',
 'bokmål':'Norwegian','bokmal':'Norwegian','norwegian bokmal':'Norwegian','norwegian bokmål':'Norwegian','bokmål norwegian':'Norwegian','nynorsk':'Norwegian','norsk':'Norwegian',
 'flemish':'Dutch','netherlands':'Dutch','sinhalese':'Sinhala','afaan oromo':'Oromo','afaan oromoo':'Oromo','afan oromo':'Oromo',
 'pakistani urdu':'Urdu','roman urdu':'Urdu','urdū':'Urdu','luxembourish':'Luxembourgish','luxembourgesch':'Luxembourgish',
 'modern standard arabic':'Arabic','lebanese arabic':'Arabic','darija':'Arabic','modern standard greek':'Greek','modern greek':'Greek',
 'scottish english':'English','irish english':'English','pakistani english':'English','australian english':'English',
 'philippine english':'English','swiss german':'German','deutsch':'German','european portuguese':'Portuguese','português':'Portuguese',
 'standard chinese':'Chinese','traditional chinese':'Chinese','chinese mandarin':'Chinese','chinese, mandarin':'Chinese',
 'north macedonian':'Macedonian','kosovan albanian':'Albanian','română':'Romanian','român':'Romanian','panjabi':'Punjabi',
 'central thai':'Thai','isan thai':'Thai','isan':'Thai','amarigna':'Amharic','binisaya':'Cebuano',
 'serbo-croatian':'Serbian','bosnian/croatian/serbian':'Bosnian','montenegrin / serbian':'Montenegrin','montenegrin serbian':'Montenegrin',
}
ISO_NAMES = dict(zip(
 'en fr de es pt it zh ja ko ar ru uk be bg bs hr sr mk sl sk cs pl ro hu el tr nl sv da no nn fi is et lv lt sq ca hi bn mr ta kn pa ur fa ne si my th vi id ms tl sw am uz kk ps sd ceb lb rm'.split(),
 'English French German Spanish Portuguese Italian Chinese Japanese Korean Arabic Russian Ukrainian Belarusian Bulgarian Bosnian Croatian Serbian Macedonian Slovenian Slovak Czech Polish Romanian Hungarian Greek Turkish Dutch Swedish Danish Norwegian Norwegian Finnish Icelandic Estonian Latvian Lithuanian Albanian Catalan Hindi Bengali Marathi Tamil Kannada Punjabi Urdu Persian Nepali Sinhala Burmese Thai Vietnamese Indonesian Malay Tagalog Swahili Amharic Uzbek Kazakh Pashto Sindhi Cebuano Luxembourgish Romansh'.split()))

def norm(raw):
    raw = str(raw or '').strip()
    raw = re.sub(r'\s*\(.*', '', raw).strip()
    return ALIASES.get(raw.lower(), raw.title())

# lid.176 cannot reliably separate Malay from Indonesian (two mutually intelligible standards), and
# Lingua returns BOKMAL for Norwegian. Danish and Norwegian are distinct and are deliberately NOT merged.
FAMILIES = [
    {'Bosnian', 'Croatian', 'Serbian', 'Montenegrin'},
    {'Malay', 'Indonesian'},
    {'Norwegian', 'Bokmal', 'Nynorsk'},
]
def matches(found, target):
    if found == target:
        return True
    return any(target in f and found in f for f in FAMILIES)

MIN_CHARS = 12          # below this, LID is noise rather than signal
_model = _lingua = None

def init(ftz=None, deps=None):
    """Load the fastText lid.176 model (path from the argument or PF_LID_MODEL). The optional deps argument adds a
    directory with the fasttext/lingua packages to sys.path."""
    global _model
    if deps:
        sys.path.insert(0, deps)
    import fasttext
    _model = fasttext.load_model(ftz or os.environ["PF_LID_MODEL"])

def detect(text):
    """fastText lid.176 at p>=0.5, Lingua fallback; normalized language name, TooShort or Unknown."""
    global _lingua
    t = (text or '').strip()
    if len(t) < MIN_CHARS:
        return 'TooShort'
    flat = t.replace('\n', ' ')
    try:
        p = _model.f.predict(flat + '\n', 1, 0.0, 'strict')
        if p and p[0][0] >= .5:
            answer = ISO_NAMES.get(p[0][1].replace('__label__', ''))
            if answer:
                return answer
    except Exception:
        pass
    if _lingua is None:
        from lingua import LanguageDetectorBuilder
        _lingua = LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()
    try:
        answer = _lingua.detect_language_of(t)
    except Exception:
        answer = None
    return norm(answer.name) if answer else 'Unknown'
