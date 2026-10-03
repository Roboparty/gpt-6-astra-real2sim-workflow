"""Freeze exact LPIPS image pairs and fixed-view previews for repair ablations."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--variants', nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    pairs, held = [], []
    expected = None
    source_hashes = {}
    for name in a.variants:
        rows = json.loads((a.root / name / 'render_manifest.json').read_text())
        identities = [(r['frame_id'], r['split']) for r in rows]
        assert len(rows) == 13 and len(set(identities)) == 13
        if expected is None:
            expected = identities
        assert identities == expected, 'Mismatched view sets or order'
        held.append([r for r in rows if r['split'] == 'heldout'])
        assert len(held[-1]) == 8
        for row in rows:
            assert sha(row['render']) == row['render_sha256']
            pair = dict(method=name, frame_id=row['frame_id'], split=row['split'])
            for kind in ['source', 'render']:
                image = Image.open(row[kind]).convert('RGB')
                if kind == 'source':
                    image = image.resize(tuple(row['size']), Image.Resampling.LANCZOS)
                assert image.size == tuple(row['size'])
                filename = name + '_' + row['frame_id'] + '_' + kind + '.png'
                image.save(a.out / filename)
                pair[kind], pair[kind + '_sha256'] = filename, sha(a.out / filename)
                if kind == 'source':
                    key = (row['frame_id'], row['split'])
                    source_hashes.setdefault(key, pair['source_sha256'])
                    assert source_hashes[key] == pair['source_sha256'], 'Source image changed between variants'
            pairs.append(pair)
    (a.out / 'pairs.json').write_text(json.dumps(pairs, indent=2))
    # The same first/fourth/eighth formerly heldout views as the frozen baseline.
    for filename, indices in [('comparison_preview.jpg', [0, 3, 7]), ('all_exposed_test.jpg', list(range(8)))]:
        sheet = Image.new('RGB', (400 * (1 + len(held)), 305 * len(indices)), '#eeeeee')
        draw = ImageDraw.Draw(sheet)
        for y, index in enumerate(indices):
            rows = [held[0][index]] + [group[index] for group in held]
            for x, row in enumerate(rows):
                label = 'REAL' if x == 0 else a.variants[x - 1]
                image = Image.open(row['source' if x == 0 else 'render']).convert('RGB')
                image.thumbnail((400, 275))
                sheet.paste(image, (x * 400, y * 305 + 25))
                draw.text((x * 400 + 5, y * 305 + 5), label + ' ' + row['frame_id'], fill='black')
        sheet.save(a.out / filename, quality=91)
    print('FROZEN_APPEARANCE_PAIRS', len(pairs))


if __name__ == '__main__':
    main()
