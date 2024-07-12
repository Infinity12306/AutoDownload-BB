import selenium
import pdb
import requests
import os
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from urllib.parse import unquote, urlparse, parse_qs
from typing import List
from tqdm import tqdm

def login(driver, username, password):
    '''
    Login in and enter the main page
    '''
    # locate the username and password input fields
    username_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'user_name'))
    )
    password_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'password'))
    )
    username_input.send_keys(f'{username}')
    password_input.send_keys(f'{password}')

    # click the login button
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//input[@id="logon_button"]'))
    )
    login_button.click()

    # click the button for allowing cookie collection
    cookie_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@id='agree_button']"))
    )
    cookie_button.click()
    return None

def set_cookies(driver: webdriver.Chrome):
    '''
    Copy the cookies in selenium driver to the requests.Session() so that the session
    will also be authorized
    '''
    session = requests.Session()
    selenium_cookies = driver.get_cookies()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    return session

def enter_course_page(driver: webdriver.Chrome, course_name):
    '''
    Enter the course page and return the main page window handle 
    for getting back to the main page
    '''
    # wait until the popup window for cookie collection disappers
    WebDriverWait(driver, 10).until(
        EC.invisibility_of_element_located((By.ID, 'agree_button'))
    )
    # locate the element corresponding to the course
    course_link = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//a[contains(text(), '{course_name}')]"))
    )
    course_url = course_link.get_attribute('href')
    # open the course page in a new window
    current_window = switch_to(driver, course_url)
    return current_window

def download_materials(driver:webdriver.Chrome, session:requests.Session, 
                       download_channel_lst, download_dir):
    '''
    Download the materials, including pdf, ppt and other files with supported suffix.
    '''
    channel_link = enter_channel(driver, download_channel_lst)
    if channel_link is not None:
        recursive_download(driver, session, channel_link.get_attribute('href'), download_dir)
    return None

def download_recordings(driver:webdriver.Chrome, session:requests.Session,
                        download_channel, download_dir):
    '''
    Download all the recordings of a class
    '''
    # locate the element for "课堂实录" channel and open its href in a new window
    # try:
    #     files_link = WebDriverWait(driver, 10).until(
    #         EC.presence_of_element_located((By.XPATH, f"//a[span[text()='{download_channel}']]"))
    #     )
    # except:
    #     print("'课堂实录' channel is not found!")
    #     return None
    current_url = driver.current_url
    parsed_url = urlparse(current_url)
    url_params = parse_qs(parsed_url.query)
    course_id = url_params.get('course_id', [None])[0]
    recording_url = f'https://course.pku.edu.cn/webapps/bb-streammedia-hqy-BBLEARN/videoList.action?course_id={course_id}&mode=view'
    course_window = switch_to(driver, recording_url)
    # get the total number of recordings
    class_num_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[@class='pagingprefs']//strong[1]"))
    )
    class_num = int(class_num_element.text) # total number of lecture recordings
    # get the max index of recording in current page
    page_max_class_index_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[@class='pagingprefs']//strong[3]"))
    )
    page_max_class_index = int(page_max_class_index_element.text)
    # repeat the process of downloading recordings in current page and switching to next page
    # until max index recording in current is equal to the total number of recordings
    while page_max_class_index <= class_num:
        # locate all the elements containing the recording urls and download them
        a_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[@class='inlineAction']"))
        )
        download_recordings_page(driver, session, a_elements, download_dir)
        # this is the real exit where loop ends
        if page_max_class_index == class_num:
            break
        # get the next page button and switch to the next page
        next_page_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//a[@id=listContainer_nextpage_bot']"))
        )
        # next_page_url = relative_url_to_absolute(next_page_button.get_attribute('href')) # used if the href is relative url
        next_page_url = next_page_button.get_attribute('href')
        driver.close()
        switch_to(driver, next_page_url)
    # switch back to the course page
    switch_back(driver, course_window)
    return None

def download_recordings_page(driver:webdriver.Chrome, session:requests.Session,
                             a_elements: List[WebElement], download_dir):
    '''
    Download all recordings in current page 
    '''
    # a_elements store all the elements containing the recordings
    num_lecs = len(a_elements)
    # download recordings one by one
    for a in tqdm(a_elements, total=num_lecs):
        # open the recording page in a new window
        current_window = switch_to(driver, a.get_attribute('href'))
        # switch to the iframe containing the video player and the download link button
        # without the switch, the download link button can not be selected in the outer html
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='yjapise.pku.edu.cn']"))
        )
        driver.switch_to.frame(iframe)
        # locate the "复制下载地址" button
        buttons = []
        while len(buttons) < 2:
            buttons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".el-button"))
            )
        button = buttons[1]
        # get the download link binded to the button
        script = "return arguments['0'].__vue__.$vnode.data.directives[0]['value'];"
        result = WebDriverWait(driver, 10).until(
            lambda driver: driver.execute_script(
                script, button)
        )
        # the raw download link can not be used to download directly
        # we need to transform it to a valid download link
        download_url = get_download_url(result)
        # save the recording
        lec_idx = num_lecs - a_elements.index(a)
        print(f'Downloading lec_{lec_idx}.mp4, it may take a while')
        with open(os.path.join(download_dir, f'lec_{lec_idx}.mp4'), 'wb') as file:
            response = session.get(download_url)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  # 1 Kilobyte
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True, desc=f'lec_{lec_idx}.mp4')
            for data in response.iter_content(block_size):
                file.write(data)
                progress_bar.update(len(data))
            progress_bar.close()
            print(f'lec_{lec_idx}.mp4 downloaded!')
        # open the recording page and switch back to the recording list page
        switch_back(driver, current_window)
    return None

def download_homework(driver:webdriver.Chrome, session:requests.Session,
                      download_channel_lst, download_dir):
    '''
    Download files in the homework channel
    '''
    # locate the "课程作业" channel and open its href in a new window
    channel_link = enter_channel(driver, download_channel_lst)
    if channel_link is not None:
        recursive_download(driver, session, channel_link.get_attribute('href'), download_dir)
    return None

def switch_to(driver:webdriver.Chrome, new_window_url):
    '''
    Open new_window_url in a new window and return the current window handle for switching back
    '''
    # save the current window handle
    current_window = driver.current_window_handle
    # open the new_winodw_url in a new window
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])
    driver.get(new_window_url)
    # return the saved handle for switching back
    return current_window

def switch_back(driver:webdriver.Chrome, old_window):
    '''
    Close current window and switch back to the old window
    '''
    # close current window
    driver.close()
    # switch back to the saved handle
    driver.switch_to.window(old_window)
    return None

def get_download_url(raw_url):
    '''
    Python version for javascript code in https://leohlee.github.io/pkuVideo.html
    '''
    mp4_pattern = re.compile(r'http.+\.mp4\?.*')
    m3u8_pattern = re.compile(r'https://resourcese\.pku\.edu\.cn/play/0/harpocrates/\d+/\d+/\d+/([a-zA-Z0-9]+)/\d+/playlist\.m3u8\?.*')
    download_url = None
    if mp4_pattern.match(raw_url):
        # can directly be used to download
        download_url = raw_url
    elif m3u8_pattern.match(raw_url):
        # extract the hash value and download it from the official source website
        matches = m3u8_pattern.match(raw_url)
        hash_value = matches.group(1)
        download_url = f'https://course.pku.edu.cn/webapps/bb-streammedia-hqy-BBLEARN/downloadVideo.action?resourceId={hash_value}'
    else:
        raise RuntimeError(f'Unrecognized URL: {raw_url}')
    return download_url

def relative_url_to_absolute(relative_url):
    '''
    Transform relative url(without base url) to a complete url
    '''
    # relative_url is the url without the base url
    # use current window's url to get the missing base url
    parsed_url = urlparse(driver.current_url)
    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
    absolute_url = base_url + relative_url
    return absolute_url

def enter_channel(driver:webdriver.Chrome, download_channel_lst) -> WebElement | None:
    try:
        conditions = "or".join([f"text()='{channel}'" for channel in download_channel_lst])
        channel_link = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.XPATH, f"//li[contains(@id, 'paletteItem')]//a[span[{conditions}]]"))
        )
        return channel_link
    except:
        channels_lst = WebDriverWait(driver, 1).until(
            EC.presence_of_all_elements_located((By.XPATH, f"//li[contains(@id, 'paletteItem')]//a"))
        )
        all_channels_name = [element.get_attribute('innerText') for element in channels_lst]
        print(f"'{download_channel_lst}' channels are not found among channels {all_channels_name}!")
        return None

def recursive_download(driver:webdriver.Chrome, session:requests.Session, url, download_dir):
    '''
    Recursively download all files and directories in the given url
    '''
    last_window = switch_to(driver, url)
    try:
        a_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//ul[@id='content_listContainer']//a"))
        )
    except:
        print(f"No downloadable files or directories in {unquote(url)}!")
    href_lst = [a.get_attribute('href') for a in a_elements]
    href_lst = [relative_url_to_absolute(href) for href in href_lst if href.startswith('/')]
    # download all the materials
    for href in href_lst:
        response = session.get(url)
        file_name = response.url.split('/')[-1]
        if not file_name.endswith(('.pdf', '.zip', '.doc', '.docx', '.ppt', '.pptx')):
            recursive_download(driver, session, href)
        else:
            download_file_from_response(response, file_name, download_dir)
    # close current window and switch back to the last window
    switch_back(driver, last_window)
    return None
    

def download_file_from_response(response: requests.Response, file_name, download_dir):
    '''
    Download a file from the response of its corresponding url
    '''
    with open(os.path.join(download_dir, unquote(file_name)), 'wb') as file:
        file.write(response.content)
        print(f"{unquote(file_name)} downloaded!")
    return None

if __name__ == '__main__':
    driver = webdriver.Chrome(service=Service(os.path.join('.', 'chromedriver.exe')))
    driver.get('https://course.pku.edu.cn/webapps/bb-sso-BBLEARN/login.html')

    # Note: all you need to enter or modify include
        # username 
        # password
        # course_list: a list of substring of course name sufficient to uniquely identify the course you want to archive
        # download_channel_lst: Chinese name of the channel you want to download, must be a subset of ['课堂实录', '教学内容', '课程作业']
        # download_dir_lst: English name of the channel you want to download, must be a subset of ['recordings', 'materials', 'homework']
    # Note: the length of download_channel_lst and download_dir_lst should be the same
    # Note: the course name in the *_ignore_list must be identical to the course name in the course_list
    username = 'xxx'
    password = 'xxx'
    course_lst = ['JS语言Web程序设计(23-24学年第2学期)', 'Rust程序设计(23-24学年第2学期)', '人工智能中的编程(23-24学年第1学期)', '图形学物理仿真(23-24学年第2学期)', '几何计算前沿(23-24学年第2学期)', '大规模语言模型与自然语言生成(23-24学年第2学期)', '数据库概论（实验班）(23-24学年第2学期)', '角色动画与运动仿真(23-24学年第2学期)',
                    '近现代物理导论 II(23-24学年第2学期)', 'AI中的数学(21-22学年第2学期)', '多智能体系统(22-23学年第2学期)', '机器学习(21-22学年第2学期)', '生成模型基础(23-24学年第1学期)', '计算机网络(23-24学年第1学期)']
    download_channel_lst = ['课堂实录', ['教学内容', '内容', '讲义'], ['课程作业', '作业']] # Currently only the three channels are supported
    download_dir_lst = ['recordings', 'materials', 'homework']
    recording_ignore_list = ['JS语言Web程序设计(23-24学年第2学期)', 'Rust程序设计(23-24学年第2学期)', '人工智能中的编程(23-24学年第1学期)', '图形学物理仿真(23-24学年第2学期)', '多智能体系统(22-23学年第2学期)', 'AI中的数学(21-22学年第2学期)',
                                ]
    material_ignore_list = []
    homework_ignore_list = []
    assert len(download_channel_lst) == len(download_dir_lst), 'Length of download_channel and download_dir should be the same'

    # login in and enter the main course list page
    login(driver, username, password)
    # set cookies of the session for downloading files as authenticated user
    session = set_cookies(driver)

    # remove the semester suffix of the course name in the ignore list
    recording_ignore_list = [course_name.split('(')[0] for course_name in recording_ignore_list]
    material_ignore_list = [course_name.split('(')[0] for course_name in material_ignore_list]
    homework_ignore_list = [course_name.split('(')[0] for course_name in homework_ignore_list]

    # iterate over the course list and download all files in all channels you specify
    for course_name in course_lst:
        course_name = course_name.split('(')[0]
        print(f"Downloading course {course_name}: ")
        print('*'*50)
        # open the course page in a new window
        main_page_window = enter_course_page(driver, course_name)
        for download_channel, download_dir in zip(download_channel_lst, download_dir_lst):
            # create the download directory if not exists
            real_download_dir = os.path.join('.', course_name, download_dir)
            os.makedirs(real_download_dir, exist_ok=True)
            if download_dir == 'materials' and not course_name in material_ignore_list:
                download_materials(driver, session, download_channel, real_download_dir)
            elif download_dir == 'recordings' and not course_name in recording_ignore_list:
                download_recordings(driver, session, download_channel, real_download_dir)
            elif download_dir == 'homework' and not course_name in homework_ignore_list:
                download_homework(driver, session, download_channel, real_download_dir)
            else:
                raise NotImplementedError('Currently only recordings, materials and homework downloading are supported')
        # close the course page and switch back to the main course list page
        switch_back(driver, main_page_window)
