# FLOAD Google Drive Data Layout

Google Drive folder:

https://drive.google.com/drive/folders/1DxYZwzf4QliiFzZdf32HQ6U0sHpMQBnC

Recommended structure:

```text
FLOAD_DATA/
  raw/
    07_cctv/
      AI Hub 07 CCTV original video and label files
    135_busan_flood/
      AI Hub 135 Busan flood risk image and label files
  processed/
    Optional processed frames or resized images
  exports/
    Training CSV files
  docs/
    Data notes and sharing instructions
```

Rules:

- Put large AI Hub files in Google Drive, not GitHub.
- Put API data such as rainfall and flood history in Supabase.
- Keep paths in CSV relative to `FLOAD_DATA`.
- Each teammate sets `DATASET_DIR` to their local Google Drive folder path.

Example:

```text
DATASET_DIR=/Users/name/Google Drive/FLOAD_DATA
```
