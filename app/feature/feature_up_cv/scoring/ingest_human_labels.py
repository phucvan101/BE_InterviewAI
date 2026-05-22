import csv
from pathlib import Path


def ingest_and_write(review_csv: Path = Path('label_candidates_for_review.csv'), out_csv: Path = Path('labeled_for_training.csv')):
    if not review_csv.exists():
        # Fallback to auto-generated candidates
        review_csv = Path('label_candidates.csv')
        if not review_csv.exists():
            raise FileNotFoundError(f"No review CSV found at {review_csv} or label_candidates.csv")

    with review_csv.open('r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    out_fields = [
        'jd_file', 'project_index', 'project_name', 'project_description',
        'label_norm', 'sem_sim', 'ce_score', 'human_used', 'human_label_raw', 'human_notes'
    ]

    human_count = 0
    auto_count = 0

    with out_csv.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields)
        writer.writeheader()
        for r in rows:
            hraw = (r.get('human_label') or '').strip()
            if hraw != '':
                try:
                    hval = float(hraw)
                    # expect 0/1/2 — normalize to [0.0, 1.0]
                    label_norm = max(0.0, min(1.0, hval / 2.0))
                    human_used = True
                    human_count += 1
                except Exception:
                    # if human label malformed, fallback to current_label
                    label_norm = float(r.get('current_label') or 0.0)
                    human_used = False
                    auto_count += 1
            else:
                label_norm = float(r.get('current_label') or 0.0)
                human_used = False
                auto_count += 1

            out_row = {
                'jd_file': r.get('jd_file', ''),
                'project_index': r.get('project_index', ''),
                'project_name': r.get('project_name', ''),
                'project_description': r.get('project_description', ''),
                'label_norm': label_norm,
                'sem_sim': r.get('sem_sim', ''),
                'ce_score': r.get('ce_score', ''),
                'human_used': human_used,
                'human_label_raw': hraw,
                'human_notes': r.get('human_notes', ''),
            }
            writer.writerow(out_row)

    print(f'WROTE: {out_csv}  human_labels={human_count} auto_labels={auto_count}')
    return out_csv


def main():
    ingest_and_write()


if __name__ == '__main__':
    main()
