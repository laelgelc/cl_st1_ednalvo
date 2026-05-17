# Basic test run on a small sample (test mode enabled by default, limit 5):

python transcribe_image_handwriting.py \
    --model gpt-5.5 \
    --input-dir corpus/01_poc_dataset \
    --output-dir corpus/02_extracted

# Process all supported images without test mode, using 4 workers:

python transcribe_image_handwriting.py \
    --model gpt-5.5 \
    --input-dir corpus/01_poc_dataset \
    --output-dir corpus/02_extracted \
    --no-test-mode \
    --workers 4

# Force reprocessing of all images, overriding existing `.txt` files:

python transcribe_image_handwriting.py \
    --model gpt-5.5 \
    --input-dir corpus/01_poc_dataset \
    --output-dir corpus/02_extracted \
    --no-test-mode \
    --workers 4 \
    --reprocess

# Process all supported images without test mode, using 4 workers, on an EC2 instance:

nohup bash run_python_ec2.sh \
    transcribe_image_handwriting.py \
        --model gpt-5.5 \
        --input-dir corpus/01_poc_dataset \
        --output-dir corpus/02_extracted \
        --no-test-mode \
        --workers 4 \
> process_output.log 2>&1 &
