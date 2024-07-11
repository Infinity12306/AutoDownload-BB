# Introduction
Use selenium to automatically download homework files and course materials (support files with suffix .pdf ,.zip, .doc, .docx, .ppt, .pptx), and recordings from the course website.

# Declaration
This project is only for learning and communication, and the user is responsible for all consequences caused by using this project. Please use this project in a legal way.

# Usage
1. Install the required packages
```bash
pip install selenium requests tqdm
```

2. Input your own authentication data and target courses and channels in [`archive.py`](https://github.com/Infinity12306/AutoDownload-BB/blob/main/archive.py#L307)

3. Run the archive.py
```bash
python archive.py
```

The download progress is recorded in the console along the way. For large files like course recordings, a progress bar is displayed for you to easily track the downloading. All downloaded files are saved in the corresponding course folder with a hierachy like

```
AutoDownload-BB
    |-archive.py
    |
    |-CourseName1
    |   ├── materials
    |   │   ├── file1.pdf
    |   │   ├── file2.zip
    |   │   └── ...
    |   ├── homework
    |   │   ├── hw1.pdf
    |   │   ├── hw2.zip
    |   │   └── ...
    |   └── recordings
    |       ├── rec1.mp4
    |       ├── rec2.mp4
    |       └── ...
    |   
    |-CourseName2
    |   ├── ...
    |
    |-...
```