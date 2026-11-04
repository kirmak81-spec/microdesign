"""Conservative detection of archived thumbnail/original pairs within one product."""

import hashlib
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageChops, ImageOps, ImageStat


def imported_names(root, original):
    identity = hashlib.sha256(str(original.relative_to(root)).encode()).hexdigest()[:24]
    base = Path("imported") / identity[:2] / identity
    return {str(base) + ".webp", str(base) + original.suffix.lower()}


def _sample(path):
    with Image.open(path) as image:
        image.draft("RGB", (256, 256))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((256, 256))
        return image.resize((32, 32), Image.Resampling.LANCZOS)


def _dhash(image):
    pixels = list(image.convert("L").resize((9, 8)).getdata())
    return sum(
        (pixels[y * 9 + x] > pixels[y * 9 + x + 1]) << (y * 8 + x)
        for y in range(8)
        for x in range(8)
    )


def preview_pairs(images, folder):
    """Return only URL/name/size pairs also confirmed by visual similarity.

    No changes to originals. A thumbnail without a verified full-size counterpart
    is deliberately preserved. Near-identical photographs with different names
    are not merged.
    """
    folder = folder.resolve()
    groups = defaultdict(list)
    for index, record in enumerate(images):
        url = record.get("source_url") or ""
        parsed = urlsplit(url)
        name = unquote(parsed.path.rsplit("/", 1)[-1])
        file = (folder / record["file"]).resolve()
        if not name or not file.is_relative_to(folder) or not file.is_file():
            continue
        groups[name].append((index, "/pic/" in parsed.path, file))
    result = []
    for group in groups.values():
        originals = []
        for index, is_preview, file in group:
            if is_preview:
                continue
            try:
                with Image.open(file) as image:
                    width, height = image.size
                originals.append((width * height, index, file, width, height))
            except (OSError, ValueError, Image.DecompressionBombError):
                continue
        if not originals:
            continue
        _, keep, original, width, height = max(originals)
        original_sample = None
        for index, is_preview, file in group:
            if not is_preview:
                continue
            try:
                with Image.open(file) as image:
                    small_width, small_height = image.size
                if not (
                    width > small_width
                    and height > small_height
                    and width * height >= 4 * small_width * small_height
                ):
                    continue
                if abs((width / height) / (small_width / small_height) - 1) > 0.03:
                    continue
                if original_sample is None:
                    original_sample = _sample(original)
                sample = _sample(file)
                difference = (
                    sum(
                        ImageStat.Stat(
                            ImageChops.difference(original_sample, sample)
                        ).mean
                    )
                    / 3
                )
                distance = (_dhash(original_sample) ^ _dhash(sample)).bit_count()
                if difference <= 12 and distance <= 8:
                    result.append(
                        {
                            "remove_index": index,
                            "keep_index": keep,
                            "difference": round(difference, 3),
                            "hash_distance": distance,
                            "preview_size": [small_width, small_height],
                            "original_size": [width, height],
                        }
                    )
            except (OSError, ValueError, Image.DecompressionBombError):
                continue
    return result
