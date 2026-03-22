"""Fix tags exceeding Etsy's 20-character limit in local listing files."""

import json
from pathlib import Path

from etsync.config import get_data_dir

MAX_TAG_LEN = 20

# Explicit mapping for tags that need manual shortening.
# Approach: drop filler words, shorten adjectives, keep SEO value.
TAG_FIXES: dict[str, str] = {
    # "european artisan/handmade" family — shorten to "eu artisan/handmade"
    "european artisan bird": "eu artisan bird art",
    "european artisan craft": "eu artisan craft",
    "european artisan flower": "eu artisan flower",
    "european artisan forging": "eu artisan forging",
    "european artisan lamp": "eu artisan lamp",
    "european artisan metal": "eu artisan metal",
    "european artisan sculpture": "eu artisan sculpture",
    "european artisan stakes": "eu artisan stakes",
    "european crafted coasters": "eu crafted coasters",
    "european handmade art": "eu handmade art",
    "european handmade craft": "eu handmade craft",
    "european handmade decor": "eu handmade decor",
    "european handmade flower": "eu handmade flower",
    "european handmade light": "eu handmade light",
    "european handmade sphere": "eu handmade sphere",
    "european handmade stake": "eu handmade stake",
    "european handmade stakes": "eu handmade stakes",
    # "architectural" → "archi" or rephrase
    "architectural garden accent": "archi garden accent",
    "architectural garden art": "archi garden art",
    "architectural metal art": "archi metal art",
    "architectural patio art": "archi patio art",
    "architectural yard feature": "archi yard feature",
    "architectural yard stakes": "archi yard stakes",
    # "housewarming" → "warming"
    "housewarming garden gift": "warming garden gift",
    "housewarming art gift": "warming art gift",
    "housewarming gift idea": "warming gift idea",
    "unique housewarming gift": "warming gift unique",
    # "weathered" → shorten
    "weathered steel sculpture": "weathered steel art",
    "weathered iron flames": "weathered iron flame",
    "weathered iron spirals": "weathered iron coil",
    "weathered metal coasters": "weathered coasters",
    "weathered metal reeds": "weathered metal reed",
    "weathered painted steel": "weathered painted",
    "weathered patina flower": "weathered patina art",
    "weathered patina grass": "weathered patina",
    "weathered steel bloom": "weathered bloom art",
    "weathered steel grass": "weathered steel reed",
    "weathered steel pedestal": "weathered pedestal",
    "weathered steel sphere": "weathered sphere",
    "weathered iron column": "weathered iron post",
    "weathered patina ball": "weathered patina orb",
    # "handcrafted/handforged/handwelded" → shorten
    "handcrafted bird stake": "handcraft bird stake",
    "handcrafted garden stake": "handcraft yard stake",
    "handcrafted in europe": "crafted in europe",
    "handcrafted outdoor art": "handcraft yard art",
    "handcrafted patio decor": "handcraft patio art",
    "handcrafted petal art": "handcraft petal art",
    "handcrafted reed stakes": "handcraft reed stake",
    "handcrafted twisted metal": "twisted metal art",
    "handcrafted washer art": "handcraft washer art",
    "handforged steel roses": "forged steel roses",
    "handmade bar coasters": "handmade bar coaster",
    "handwelded metal ball": "handwelded metal orb",
    "handwelded washer ball": "welded washer orb",
    "handwelded washer sphere": "welded washer sphere",
    "hand forged steel stakes": "forged steel stakes",
    # "sculpture" family — shorten
    "abstract garden sculpture": "abstract garden art",
    "abstract outdoor artwork": "abstract outdoor art",
    "abstract outdoor accent": "abstract yard accent",
    "abstract outdoor focal": "abstract focal point",
    "abstract yard feature": "abstract yard art",
    "abstract botanical metal": "botanical metal art",
    "aquatic plant sculpture": "aquatic plant art",
    "botanical yard sculpture": "botanical yard art",
    "colored patina sculpture": "colored patina art",
    "column mounted sculpture": "column mount art",
    "hemisphere base sculpture": "hemisphere base art",
    "kinetic wind sculpture": "kinetic wind art",
    "large heron sculpture": "large heron art",
    "large landscape sculpture": "large landscape art",
    "large outdoor sculpture": "large outdoor art",
    "large patio sculpture": "large patio art",
    "metal flower sculpture": "metal flower art",
    "metal grass sculpture": "metal grass art",
    "minimalist steel sculpture": "minimal steel art",
    "nature inspired metalwork": "nature metal art",
    "organic sphere sculpture": "organic sphere art",
    "outdoor floral sculpture": "outdoor floral art",
    "outdoor sphere sculpture": "outdoor sphere art",
    "rusted patina sculpture": "rusted patina art",
    "rustic bird sculpture": "rustic bird art",
    "rustic mantel sculpture": "rustic mantel art",
    "rustic sphere sculpture": "rustic sphere art",
    "rustic sprout sculpture": "rustic sprout art",
    "seasonal color sculpture": "seasonal color art",
    "statement garden piece": "statement garden art",
    "statement yard sculpture": "statement yard art",
    "swaying breeze sculpture": "swaying breeze art",
    "swaying wind sculpture": "swaying wind art",
    "tabletop flame sculpture": "tabletop flame art",
    "wind dancing sculpture": "wind dancing art",
    "wind swaying sculpture": "wind swaying art",
    "human height sculpture": "human height art",
    "patio flower sculpture": "patio flower art",
    "artisan bloom sculpture": "artisan bloom art",
    "contemplative yard decor": "contemplative yard",
    "everlasting metal bloom": "everlasting bloom",
    # "landscape" family
    "minimalist landscape accent": "minimal landscape",
    "naturalistic landscape art": "naturalistic garden",
    "naturalistic yard feature": "naturalistic yard",
    "unique landscape accent": "unique yard accent",
    "unique landscape feature": "unique yard feature",
    "unique landscape pillar": "unique yard pillar",
    "tall landscape statement": "tall yard statement",
    "desert landscape accent": "desert garden accent",
    "pond landscape accent": "pond garden accent",
    # "centerpiece" → shorten
    "decorative garden globe": "garden globe decor",
    "flower bed centerpiece": "flower bed accent",
    "patio art centerpiece": "patio art focal",
    "rustic patio centerpiece": "rustic patio focal",
    "spring patio centerpiece": "spring patio focal",
    "spring garden centerpiece": "spring garden focal",
    "spring garden focal point": "spring focal point",
    "unique lawn centerpiece": "unique lawn focal",
    "zen garden centerpiece": "zen garden focal",
    "zen outdoor centerpiece": "zen outdoor focal",
    # "garden" family
    "spring garden ornament": "spring garden decor",
    "spring garden planting": "spring garden plant",
    "spring garden sculpture": "spring garden art",
    "spring garden sprouts": "spring garden sprout",
    "spring landscape decor": "spring yard decor",
    "spring courtyard feature": "spring courtyard art",
    "spring flower bed decor": "spring flowerbed art",
    "garden flower focal point": "garden flower focal",
    # "industrial" family
    "industrial candle light": "industrial candle",
    "industrial candle stand": "industrial stand",
    "industrial loft decor": "industrial loft art",
    "industrial romantic decor": "industrial romance",
    "industrial steel coasters": "industrial coasters",
    "modern industrial globe": "industrial globe",
    # Various
    "ambient shadow caster": "ambient shadow lamp",
    "anniversary flower gift": "anniversary flower",
    "atmospheric table decor": "atmospheric decor",
    "cathedral inspired art": "cathedral style art",
    "chess lover garden gift": "chess garden gift",
    "collapsible kinetic art": "kinetic folding art",
    "contemplative yard decor": "contemplative decor",
    "corten sphere pedestal": "corten orb pedestal",
    "corten style candleholder": "corten candleholder",
    "corten style garden art": "corten garden art",
    "cracked paint metal art": "cracked paint metal",
    "decorative garden ball": "garden ball decor",
    "decorative lawn globes": "lawn globe decor",
    "decorative yard sphere": "yard sphere decor",
    "driveway entrance decor": "driveway decor",
    "drought tolerant decor": "drought proof decor",
    "dynamic outdoor artwork": "dynamic outdoor art",
    "engagement present unique": "engagement gift",
    "evening spotlight art": "evening light art",
    "fantasy landscape accent": "fantasy garden art",
    "fathers day gift idea": "fathers day gift",
    "floral washer pattern": "floral washer art",
    "four leaf garden stakes": "clover garden stakes",
    "gothic quatrefoil art": "gothic clover art",
    "illuminated garden feature": "illuminated garden",
    "indoor outdoor lantern": "indoor outdoor lamp",
    "indoor outdoor sphere": "indoor outdoor orb",
    "iron anniversary gift": "iron anniversary",
    "japanese garden stakes": "japanese yard stakes",
    "landscape focal point": "yard focal point",
    "large statement pendant": "statement pendant",
    "leaf sphere sculpture": "leaf sphere art",
    "loft pendant lighting": "loft pendant light",
    "low maintenance garden": "low care garden art",
    "meaningful love symbol": "love symbol art",
    "medieval garden accent": "medieval garden art",
    "meditation garden piece": "meditation garden",
    "metal fiddlehead fern": "fiddlehead fern art",
    "modern country garden": "modern country yard",
    "modern japanese decor": "modern japanese art",
    "modern landscape decor": "modern yard decor",
    "modern landscape stakes": "modern yard stakes",
    "modern yard sculpture": "modern yard art",
    "no maintenance garden art": "no care garden art",
    "office desk sculpture": "office desk art",
    "openwork garden balls": "openwork garden orbs",
    "openwork metal sphere": "openwork metal orb",
    "patio focal sculpture": "patio focal art",
    "patio statement piece": "patio statement art",
    "patio walkway feature": "patio walkway art",
    "perforated metal lantern": "perforated lantern",
    "premium outdoor art set": "premium outdoor set",
    "quatrefoil metal stake": "quatrefoil stake",
    "refracted light decor": "refracted light art",
    "restaurant lighting fixture": "restaurant lighting",
    "restaurant table decor": "restaurant decor",
    "rustic clover yard art": "rustic clover art",
    "rustic outdoor ornament": "rustic yard ornament",
    "rustic patina artwork": "rustic patina art",
    "rustic yard installation": "rustic yard install",
    "samurai inspired decor": "samurai style decor",
    "sculptural candleholder": "sculptural candle",
    "sculptural hanging lamp": "sculptural hang lamp",
    "sculptural light object": "sculptural light art",
    "seasonal garden accent": "seasonal garden art",
    "shamrock metal stakes": "shamrock metal stake",
    "sideboard statement piece": "sideboard statement",
    "sixth anniversary iron": "sixth anniversary",
    "spring bloom ornament": "spring bloom decor",
    "spring evening accent": "spring evening art",
    "spring planting accent": "spring plant accent",
    "statement garden installation": "statement install",
    "steel plant stake set": "steel plant stakes",
    "steel sphere candleholder": "steel sphere candle",
    "swaying yard ornament": "swaying yard decor",
    "symbolic metal artwork": "symbolic metal art",
    "tall metal garden stakes": "tall metal stakes",
    "tall outdoor ornament": "tall outdoor decor",
    "terrace pergola light": "terrace pergola lit",
    "terrace statement piece": "terrace statement",
    "tsuba sword guard art": "tsuba guard art",
    "unique groomsmen gift": "groomsmen gift",
    "unique lawn ornament set": "unique lawn set",
    "unique yard statement": "unique yard accent",
    "wabi sabi garden accent": "wabi sabi garden",
    "wabi sabi home accent": "wabi sabi home art",
    "wabi sabi landscape art": "wabi sabi yard art",
    "wabi sabi outdoor art": "wabi sabi outdoor",
    "welded leaf sculpture": "welded leaf art",
    "whimsical garden feature": "whimsical garden",
    "whimsical yard sculpture": "whimsical yard art",
    "whiskey bar accessories": "whiskey bar gear",
    "wind swaying ornament": "wind sway ornament",
    "wonderland inspired decor": "wonderland decor",
    "zen water garden accent": "zen water garden",
    "botanical metal decor": "botanical metal art",
    "asian garden ornament": "asian garden decor",
}


def shorten_tag(tag: str) -> str:
    """Shorten a tag to fit within the Etsy limit."""
    if len(tag) <= MAX_TAG_LEN:
        return tag
    if tag in TAG_FIXES:
        fixed = TAG_FIXES[tag]
        assert len(fixed) <= MAX_TAG_LEN, f"Fix for '{tag}' is still too long: '{fixed}' ({len(fixed)})"
        return fixed
    # Fallback: truncate at last word boundary
    words = tag.split()
    result = words[0]
    for word in words[1:]:
        candidate = result + " " + word
        if len(candidate) > MAX_TAG_LEN:
            break
        result = candidate
    return result


def fix_listing_tags(path: Path) -> tuple[int, int]:
    """Fix long tags in a listing file. Returns (total_tags, fixed_count)."""
    data = json.loads(path.read_text())
    tags = data.get("tags", [])
    fixed = 0
    new_tags = []
    for tag in tags:
        if len(tag) > MAX_TAG_LEN:
            new_tag = shorten_tag(tag)
            if new_tag != tag:
                fixed += 1
            new_tags.append(new_tag)
        else:
            new_tags.append(tag)
    if fixed > 0:
        data["tags"] = new_tags
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return len(tags), fixed


def main() -> None:
    listings_dir = get_data_dir() / "listings"
    total_fixed = 0
    total_listings = 0

    for child in sorted(listings_dir.iterdir()):
        if child.suffix == ".json" and child.stem.isdigit():
            total_tags, fixed = fix_listing_tags(child)
            if fixed > 0:
                print(f"  {child.stem}: fixed {fixed}/{total_tags} tags")
                total_fixed += fixed
                total_listings += 1

    print(f"\nFixed {total_fixed} tags across {total_listings} listings")

    # Verify no remaining violations
    remaining = 0
    for child in sorted(listings_dir.iterdir()):
        if child.suffix == ".json" and child.stem.isdigit():
            data = json.loads(child.read_text())
            for tag in data.get("tags", []):
                if len(tag) > MAX_TAG_LEN:
                    print(f"  STILL LONG: {child.stem}: \"{tag}\" ({len(tag)})")
                    remaining += 1

    if remaining:
        print(f"\n{remaining} tags still exceed {MAX_TAG_LEN} chars!")
    else:
        print("\nAll tags are within the 20-character limit.")


if __name__ == "__main__":
    main()
