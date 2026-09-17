---
license: cc-by-nc-sa-4.0
task_categories:
- summarization
- text-generation
language:
- en
tags:
- municipal
- meeting
- transcripts
- benchmark
- long-context
size_categories:
- 10M<n<100M
---
## Overview

MeetingBank, a benchmark dataset created from the city councils of 6 major U.S. cities to supplement existing datasets. It contains 1,366 meetings with over 3,579 hours of video, as well as transcripts, PDF documents of meeting minutes, agenda, and other metadata. On average, a council meeting is 2.6 hours long and its transcript contains over 28k tokens, making it a valuable testbed for meeting summarizers and for extracting structure from meeting videos. The datasets contains 6,892 segment-level summarization instances for training and evaluating of performance.

## Data Structure
```json
{
  "id": 0,
  "uid": "SeattleCityCouncil_06132016_Res 31669",
  "summary": "A RESOLUTION encouraging as a best practice ...",
  "transcript": "The report of the Civil Rights, Utilities, Economic ..."
}

```

## Usage
```python
from datasets import load_dataset
meetingbank = load_dataset("huuuyeah/meetingbank")

train_data = meetingbank['train']
test_data = meetingbank['test']
val_data = meetingbank['validation']

def generator(data_split):
  for instance in data_split:
    yield instance['id'], instance['summary'], instance['transcript']
```

## Acknowledgement

Please cite the following paper in work that makes use of this dataset:

[MeetingBank: A Benchmark Dataset for Meeting Summarization](https://arxiv.org/abs/2305.17529)\
Yebowen Hu, Tim Ganter, Hanieh Deilamsalehy, Franck Dernoncourt, Hassan Foroosh, Fei Liu\
In main conference of Association for Computational Linguistics (ACL'23), Toronto, Canada.

## Bibtex
```
@inproceedings{hu-etal-2023-meetingbank,
    title = "MeetingBank: A Benchmark Dataset for Meeting Summarization",
    author = "Yebowen Hu and Tim Ganter and Hanieh Deilamsalehy and Franck Dernoncourt and Hassan Foroosh and Fei Liu",
    booktitle = "Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)",
    month = July,
    year = "2023",
    address = "Toronto, Canada",
    publisher = "Association for Computational Linguistics",
}
```


## Multi-media Resources

MeetingBank dataset will be hosted at Zenodo. The audio files of each meeting will be hosted individually on Huggingface. All resources will includes meeting audio, transcripts, meetingbank main JSON file, summaries from 6 systems and human annotations.

**Text & Audio**: [zenodo](https://zenodo.org/record/7989108), Huggingface([splits](https://huggingface.co/datasets/huuuyeah/meetingbank), [audio&transcripts](https://huggingface.co/datasets/huuuyeah/MeetingBank_Audio))

**Videos**: All meeting videos can be found in https://archive.org/

- [Alameda](https://archive.org/details/meetingbank-alameda), [Boston](https://archive.org/details/meetingbank-boston), [Denver](https://archive.org/details/meetingbank-denver), [Long Beach](https://archive.org/details/meetingbank-long-beach) ,[King County](https://archive.org/details/meetingbank-king-county), [Seattle](https://archive.org/details/meetingbank-seattle)

**Python Scripts**
Useful scripts and guidance can be found in github repo [MeetingBank_Utils](https://github.com/YebowenHu/MeetingBank-utils)