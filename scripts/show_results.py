#!/usr/bin/env python3
import json

with open('logs/test_results.json') as f:
    data = json.load(f)

print('Video: 2024-05-20')
print(f'Total Frames: {data["total_frames"]}')
print(f'Duration: {data["duration_sec"]:.1f} seconds')
print(f'Processing Time: {data["processing_time_sec"]:.1f} seconds')
print(f'GPU Speed: {data["total_frames"]/data["processing_time_sec"]:.1f} FPS')
print()
print('📊 DETECTION SUMMARY (>= 85% confidence)')
print('='*70)
total = 0
for tool, data_dict in sorted(data['detections_by_class'].items(), key=lambda x: x[1]['count'], reverse=True):
    count = data_dict['count']
    max_conf = data_dict['max_confidence'] * 100
    total += count
    print(f'{tool:20s}: {count:4d} times | Max conf: {max_conf:6.2f}%')
print('='*70)
print(f'TOTAL: {total} detections')
