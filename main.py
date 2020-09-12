"""---------------------------------------------------------------
                VITask | A Dynamic VTOP API server
                
        "Any fool can write code that a computer can understand. 
        Good programmers write code that humans can understand."
------------------------------------------------------------------"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.select import Select
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import db
from firebase_admin import credentials
from PIL import Image
from PIL import ImageFilter
import pandas as pd
import pickle
import re
import os
import random
import hashlib
import bcrypt
import requests
import json
import time
import datetime
import base64

# Selenium driver and Actions as global
driver = None
action = None

# Constants for Captcha Solver
CAPTCHA_DIM = (180, 45)
CHARACTER_DIM = (30, 32)
# Above values were checked from various captchas

# Initialize Flask app
app = Flask(__name__)

# Set the port for Flask app
port = int(os.environ.get('PORT', 5000))

# Change this to your secret key (can be anything, it's for extra protection)
app.secret_key = 'canada$God7972#'

# Initialize Firebase app
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(
    cred, options={'databaseURL': 'https://modified-vtop.firebaseio.com/'})

# Returns the base64 encode of Captcha


def captchashow(driver):
    captchaimg = driver.find_elements_by_xpath(
        "//*[@id='captchaRefresh']/div/img")  # [0]
    captchasrc = captchaimg[0].get_attribute("src")
    return captchasrc


def usernamecall(driver):
    username = driver.find_elements_by_xpath("//*[@id='uname']")[0]
    return username


def passwordcall(driver):
    password = driver.find_elements_by_xpath("//*[@id='passwd']")[0]
    return password


def captchacall(driver):
    captcha = driver.find_elements_by_xpath("//*[@id='captchaCheck']")[0]
    return captcha

# Magical Captcha solver by Cherub begins from here ;)


def download_captcha(num, username, driver):
    """
    Downloads and save a random captcha from VTOP website in the path provided
    num = number of captcha to save
    """
    for _ in range(num):
        base64_image = captchashow(driver)[23:]
        image_name = "./captcha/"+username+"-captcha.png"
        with open(image_name, "wb") as fh:
            fh.write(base64.b64decode(base64_image))


def remove_pixel_noise(img):
    """
    this function removes the one pixel noise in the captcha
    """
    img_width = CAPTCHA_DIM[0]
    img_height = CAPTCHA_DIM[1]

    img_matrix = img.convert('L').load()
    # Remove noise and make image binary
    for y in range(1, img_height - 1):
        for x in range(1, img_width - 1):
            if img_matrix[x, y-1] == 255 and img_matrix[x, y] == 0 and img_matrix[x, y+1] == 255:
                img_matrix[x, y] = 255
            if img_matrix[x-1, y] == 255 and img_matrix[x, y] == 0 and img_matrix[x+1, y] == 255:
                img_matrix[x, y] = 255
            if img_matrix[x, y] != 255 and img_matrix[x, y] != 0:
                img_matrix[x, y] = 255

    return img_matrix


def identify_chars(img, img_matrix):
    """
    This function identifies and returns the captcha
    """
    img_width = CAPTCHA_DIM[0]
    img_height = CAPTCHA_DIM[1]

    char_width = CHARACTER_DIM[0]
    char_height = CHARACTER_DIM[1]

    char_crop_threshold = {'upper': 12, 'lower': 44}

    bitmaps = json.load(open("bitmaps.json"))
    captcha = ""

    # loop through individual characters
    for i in range(char_width, img_width + 1, char_width):

        # crop with left, top, right, bottom coordinates
        img_char_matrix = img.crop(
            (i-char_width, char_crop_threshold['upper'], i, char_crop_threshold['lower'])).convert('L').load()

        matches = {}

        for character in bitmaps:
            match_count = 0
            black_count = 0

            lib_char_matrix = bitmaps[character]

            for y in range(0, char_height):
                for x in range(0, char_width):
                    if img_char_matrix[x, y] == lib_char_matrix[y][x] and lib_char_matrix[y][x] == 0:
                        match_count += 1
                    if lib_char_matrix[y][x] == 0:
                        black_count += 1

            perc = float(match_count)/float(black_count)
            matches.update({perc: character[0].upper()})

        try:
            captcha += matches[max(matches.keys())]
        except ValueError:
            captcha += "0"

    return captcha
# Captha solver ends here




@app.route('/', methods=['GET', 'POST'])
def index():
    global driver

    caps = DesiredCapabilities().CHROME
    caps["pageLoadStrategy"] = "eager"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(executable_path="static\chromedriver.exe", options=chrome_options)
    driver.get("http://vtop2.vitap.ac.in:8070/vtop/initialProcess/openPage")
    driver.implicitly_wait(3)
    login_button = driver.find_element_by_link_text("Login to VTOP")
    login_button.click()
    loginnext_button = driver.find_elements_by_xpath(
        "//*[@id='page-wrapper']/div/div[1]/div[1]/div[3]/div/button")[0]
    loginnext_button.click()
    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "captchaRefresh")))
    finally:
        session['timetable'] = 0
        session['classes'] = 0
        session['cgpa'] = 0
        session['gpa'] = 0

        return render_template('login.html')


# Web login route(internal don't use for anything on user side)
@app.route('/signin', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        global action
        username1 = request.form['username']
        password1 = request.form['password']

        # Solve the captcha using the captcha solver
        download_captcha(1, username1, driver)
        img = Image.open('./captcha/'+username1+'-captcha.png')
        img_matrix = remove_pixel_noise(img)
        # Store the result of solved captcha in captcha1
        captcha1 = identify_chars(img, img_matrix)

        username = usernamecall(driver)
        password = passwordcall(driver)
        captcha = captchacall(driver)
        action = ActionChains(driver)
        username.send_keys(username1)
        password.send_keys(password1)
        captcha.send_keys(captcha1)
        loginfinal_button = driver.find_elements_by_xpath(
            "//*[@id='captcha']")[0]
        loginfinal_button.click()
        driver.implicitly_wait(5)
        nav = driver.find_elements_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[1]/a")[0]
        nav.click()
        driver.implicitly_wait(3)
        profile = driver.find_element_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[1]/a")
        hover = action.move_to_element(profile)
        hover.perform()

        item = driver.find_element_by_xpath(
            "//*[@id='BtnBody21112']/div/ul/li[1]")
        item.click()
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "exTab1")))
        finally:
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            code_soup = soup.find_all(
                'td', {'style': lambda s: 'background-color: #f2dede;' in s})
            tutorial_code = [i.getText() for i in code_soup]
            code_proctor = soup.find_all(
                'td', {'style': lambda s: 'background-color: #d4d3d3;' in s})
            tutorial_proctor = [i.getText() for i in code_proctor]
            if(len(tutorial_code) != 0):
                holdname = tutorial_code[1].lower().split(" ")
            else:
                holdname = ''
            tempname = []
            for i in holdname:
                tempname.append(i.capitalize())
            finalname = (" ").join(tempname)
            tutorial_code[1] = finalname
            ref = db.reference('modified-vtop')
            tut_ref = ref.child(tutorial_code[0])
            tut_ref.set({
                tutorial_code[0]: {
                    'Name': (tutorial_code[1]),
                    'Branch': tutorial_code[18],
                    'Program': tutorial_code[17],
                    'RegNo': tutorial_code[14],
                    'AppNo': tutorial_code[0],
                    'School': tutorial_code[19],
                    'Email': tutorial_code[29],
                    'ProctorName': tutorial_proctor[93],
                    'ProctorEmail': tutorial_proctor[98]
                }
            })
            session['id'] = tutorial_code[0]
            session['name'] = tutorial_code[1]
            session['reg'] = tutorial_code[14]

        return redirect(url_for('profile'))


@app.route('/profile')
def profile():
    d=datetime.datetime.today().weekday()
    print(d)
    ref = db.reference('modified-vtop')
    name = ref.child(session['id']).child(session['id']).child('Name').get()
    school = ref.child(session['id']).child(
        session['id']).child('School').get()
    branch = ref.child(session['id']).child(
        session['id']).child('Branch').get()
    program = ref.child(session['id']).child(
        session['id']).child('Program').get()
    regno = ref.child(session['id']).child(session['id']).child('RegNo').get()
    appno = ref.child(session['id']).child(session['id']).child('AppNo').get()
    email = ref.child(session['id']).child(session['id']).child('Email').get()
    proctoremail = ref.child(session['id']).child(
        session['id']).child('ProctorEmail').get()
    proctorname = ref.child(session['id']).child(
        session['id']).child('ProctorName').get()
    return render_template('profile.html', name=name, school=school, branch=branch, program=program, regno=regno, email=email, proctoremail=proctoremail, proctorname=proctorname, appno=session['id'],day=d)


# Timetable route
@app.route('/timetable')
def timetable():
    ref = db.reference('modified-vtop')
    temp = ref.child(
        "timetable-"+session['id']).child(session['id']).child('Timetable').get()
    if(session['timetable'] == 1 or temp is not None):
        days = ref.child(
            "timetable-"+session['id']).child(session['id']).child('Timetable').get()
        sts = ref.child(
            "timetable-"+session['id']).child(session['id']).child('ss').get()
        return render_template('timetable.html', name=session['name'], id=session['id'], tt=days, ss=sts)
    else:
        nav = driver.find_elements_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[4]/a")[0]
        nav.click()
        driver.implicitly_wait(3)
        tt = driver.find_element_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[4]/a")
        hover = action.move_to_element(tt)
        hover.perform()

        item = driver.find_element_by_xpath(
            "//*[@id='BtnBody21115']/div/ul/li[9]")
        item.click()

        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "semesterSubId")))
            semlist = driver.find_element_by_xpath("//*[@id='semesterSubId']")
            semlist.click()
            hover = action.move_to_element(semlist)
            hover.perform()

            item = driver.find_element_by_xpath(
                "//*[@id='semesterSubId']/option[2]")
            try:
                select = Select(semlist)
                selected_option = select.first_selected_option
                print('\n\n\n\n\n\n\n', selected_option.text, '\n\n\n\n\n\n\n')
            except:
                print('\n\n\n\n\n\n\nws\n\n\n\n\n\n\n')
            item.click()
            viewbutton = driver.find_element_by_xpath(
                "//*[@id='studentTimeTable']/div[2]/div/button")
            viewbutton.click()

            try:
                newelement = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "timeTableStyle")))
            finally:
                page_source = driver.page_source

        finally:
            # newelement=WebDriverWait(driver,10).until(EC.presence_of_element_located((By.XPATH,"timeTableStyle")))
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            code_soup = soup.find_all('td', {'bgcolor': '#CCFF33'})
            list_soup = soup.find_all(
                'td', {'style': lambda s: 'padding: 3px; font-size: 12px; border-color: #3c8dbc;vertical-align: middle;text-align: left;' in s})
            list_code = [i.getText() for i in list_soup]
            courses = {}
            for i in list_code:
                arr = i.split("-")
                courses[arr[0].strip()] = arr[1].strip()
            tutorial_code = [i.getText() for i in code_soup]
            table = []
            for i in tutorial_code:
                if i not in table:
                    table.append(i)
            slots = {}
            time_table = {
                'A': ['Monday 09:00 09:45', 'Thursday 12:00 12:45', 'Friday 11:00 11:45'],
                'B': ['Monday 10:00 10:45', 'Wednesday 14:00 14:45', 'Friday 12:00 12:45'],
                'C': ['Monday 11:00 11:45', 'Friday 09:00 09:45', 'Saturday 14:00 14:45'],
                'D': ['Monday 14:00 14:45', 'Tuesday 09:00 09:45', 'Saturday 11:00 11:45'],
                'E': ['Monday 12:00 12:45', 'Friday 14:00 14:45', 'Saturday 10:00 10:45'],
                'F': ['Tuesday 11:00 11:45', 'Thursday 14:00 14:45', 'Saturday 09:00 09:45'],
                'G': ['Thursday 09:00 09:45', 'Saturday 12:00 12:45'],
                'H': ['Wednesday 09:00 09:45', 'Friday 10:00 10:45'],
                'TA': ['Wednesday 10:00 10:45'],
                'TB': ['Tuesday 14:00 14:45'],
                'TC': ['Thursday 10:00 10:45'],
                'TD': ['Wednesday 11:00 11:45'],
                'TE': ['Thursday 11:00 11:45'],
                'TF': ['Wednesday 12:00 12:45'],
                'TG': ['Tuesday 10:00 10:45'],
                'TH': ['Tuesday 12:00 12:45']
            }
            for i in table:
                p = []
                arr = i.split("-")
                p = [arr[1], arr[3], arr[4], courses[arr[1]], time_table[arr[0]]]
                slots[arr[0]] = p

            days = {"Monday": [], "Tuesday": [], "Wednesday": [],
                    "Thursday": [], "Friday": [], "Saturday": []}
            p = []
            for i in slots:
                for j in slots[i][4]:
                    arr = j.split(" ")
                    p = [slots[i][0], slots[i][1], slots[i]
                         [2], slots[i][3], arr[1], arr[2]]
                    if(arr[0] == "Monday"):
                        days["Monday"].append(p)
                    elif(arr[0] == "Tuesday"):
                        days["Tuesday"].append(p)
                    elif(arr[0] == "Wednesday"):
                        days["Wednesday"].append(p)
                    elif(arr[0] == "Thursday"):
                        days["Thursday"].append(p)
                    elif(arr[0] == "Friday"):
                        days["Friday"].append(p)
                    elif(arr[0] == "Saturday"):
                        days["Saturday"].append(p)
                    p = []

            ref = db.reference('modified-vtop')
            users_ref = ref.child('users')
            tut_ref = ref.child("timetable-"+session['id'])
            tut_ref.set({
                session['id']: {
                    'Timetable': days,
                    'ss': selected_option.text
                }
            })
            session['timetable'] = 1
            return render_template('timetable.html', name=session['name'], id=session['id'], tt=days, ss=selected_option.text)


# Attendance route
@app.route('/classes')
def classes():
    ref = db.reference('modified-vtop')
    temp = ref.child(
        "attendance-"+session['id']).child(session['id']).child('Attendance').get()
    if(session['classes'] == 1 or temp is not None):
        attend = ref.child(
            "attendance-"+session['id']).child(session['id']).child('Attendance').get()
        q = ref.child(
            "attendance-"+session['id']).child(session['id']).child('number').get()
        return render_template('attendance.html', name=session['name'], id=session['id'], at=attend, rn=int(q))
    else:
        nav = driver.find_elements_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[4]/a")[0]
        nav.click()
        driver.implicitly_wait(3)
        tt = driver.find_element_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[4]/a")
        hover = action.move_to_element(tt)
        hover.perform()
        item = driver.find_element_by_xpath(
            "//*[@id='BtnBody21115']/div/ul/li[10]")
        item.click()

        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "semesterSubId")))
        semlist = driver.find_element_by_xpath("//*[@id='semesterSubId']")
        driver.execute_script("arguments[0].click();", semlist)
        driver.implicitly_wait(2)

        hover = action.move_to_element(semlist)
        hover.perform()
        item = driver.find_element_by_xpath(
            "//*[@id='semesterSubId']/option[2]")
        item.click()
        viewbutton = driver.find_element_by_xpath(
            "//*[@id='viewStudentAttendance']/div[2]/div/button")
        viewbutton.click()
        try:
            try:
                newelement = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "getStudentDetails")))
            finally:
                page_source = driver.page_source

        finally:
            TD = []
            THM = []
            TA = {'Course Title': [], 'Course Type': [], 'Slot': [], 'Faculty Name': [
            ], 'Attendended Class': [], 'Total Classes': [], 'Percentage': []}
            table = driver.find_element_by_xpath(
                "/html/body/div[1]/div/div/div/div/div/div[3]/div/div/section/div/div/div[2]/div/div/div[2]/table")
            rows = table.find_elements_by_tag_name('tr')
            j = 0
            c = 0
            for row in rows:
                if j == 0:
                    for i in range(13):
                        col = row.find_elements_by_tag_name('th')[i]
                        THM.append(col.text)
                    j = 1
                    TD.insert(0, THM)
                else:
                    col = row.text
                    col = col.split('\n')
                    col = col[:13]
                    TD.append(col)

            CT = []
            Ct = []

            FN = []
            AC = []
            TC = []
            PC = []
            for i in range(1, (len(TD)-1)):
                CT.append(TD[i][2])
                Ct.append(TD[i][3])
                FN.append(TD[i][5])
                AC.append(TD[i][10])
                TC.append(TD[i][11])
                PC.append(TD[i][12])
            TA['Course Title'] = CT
            TA['Course Type'] = Ct
            TA['Faculty Name'] = FN
            TA['Attendended Class'] = AC
            TA['Total Classes'] = TC
            TA['Percentage'] = PC
            q = len(CT)
            print(TA)
            ref = db.reference('modified-vtop')
            tut_ref = ref.child("attendance-"+session['id'])
            tut_ref.set({
                session['id']: {
                    'Attendance': TA,
                    'number': q
                }
            })
        session['classes'] == 1
        return render_template('attendance.html', name=session['name'], id=session['id'], at=TA, rn=int(q))


@app.route('/grades')
def grades():
    ref = db.reference('modified-vtop')
    temp = ref.child("cgpa-"+session['id']).child(session['id']).get()
    if(session['cgpa'] == 1 or temp is not None):
        cr = ref.child("cgpa-"+session['id']).child(session['id']).get()
        print(cr.keys())
        return render_template('grades.html', name=session['name'], id=session['id'], gs=cr)
    else:
        nav = driver.find_elements_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[6]/a")[0]
        nav.click()
        driver.implicitly_wait(3)
        tt = driver.find_element_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[6]/a")
        hover = action.move_to_element(tt)
        hover.perform()

        item = driver.find_element_by_xpath(
            "//*[@id='BtnBody21117']/div/ul/li[4]")
    # driver.execute_script("arguments[0].click();", item)
        item.click()

        TD = []
        table = driver.find_element_by_xpath(
            "/html/body/div[1]/div/div/div/div/div/div[3]/div/div/section/div/div/div[2]/form/div/div/div/div[2]/div[2]/table")
        rows = table.find_elements_by_tag_name('tr')
        for row in rows:
            for i in range(10):
                col = row.find_elements_by_tag_name('td')[i]
                TD.append(col.text)
        TDD = {
            TD[0]: TD[10],
            TD[1]: TD[11],
            TD[2]: TD[12],
            TD[3]: TD[13],
            TD[4]: TD[14],
            TD[5]: TD[15],
            TD[6]: TD[16],
            TD[7]: TD[17],
            TD[8]: TD[18],
            TD[9]: TD[19]
        }
        ref = db.reference('modified-vtop')
        tref = ref.child('cgpa-'+session['id'])
        tref.set({
            session['id']: {
                TD[0]: TD[10],
                TD[1]: TD[11],
                TD[2]: TD[12],
                TD[3]: TD[13],
                TD[4]: TD[14],
                TD[5]: TD[15],
                TD[6]: TD[16],
                TD[7]: TD[17],
                TD[8]: TD[18],
                TD[9]: TD[19]
            }
        })
        session['cgpa'] = 1
        return render_template('grades.html', name=session['name'], id=session['id'], gs=TDD)


@app.route('/gpa')
def gpa():
    ref = db.reference('modified-vtop')
    temp = ref.child("gpa-"+session['id']).child(session['id']).get()
    if(session['gpa'] == 1 or temp is not None):
        days = ref.child("gpa-"+session['id']).child(session['id']).get()
        sts = ref.child("gpa-"+session['id']
                        ).child(session['id']).child('ss').get()
        return render_template('gpa.html', name=session['name'], id=session['id'], tt=days, ss=sts)
    else:
        nav = driver.find_elements_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[6]/a")[0]
        nav.click()
        driver.implicitly_wait(3)
        tt = driver.find_element_by_xpath(
            "//*[@id='button-panel']/aside/section/div/div[6]/a")
        hover = action.move_to_element(tt)
        hover.perform()

        item = driver.find_element_by_xpath(
            "//*[@id='BtnBody21117']/div/ul/li[3]")
        item.click()
        driver.implicitly_wait(3)
        page_source = driver.page_source
        print(page_source)
        # element=driver.find_element_by_xpath('/html/body/div[1]/div/div/div/div/div/div[3]/div/div/div/section/div/div/div[2]/form/div/div/div[1]/div/div/select')
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located(
            (By.XPATH, "//*[@id='main-section']/div/section/div/div/div[2]/form/div/div/div/div/div/select")))
        semlist = driver.find_element_by_xpath(
            "//*[@id='main-section']/div/section/div/div/div[2]/form/div/div/div/div/div/select")
        semlist.click()
        hover = action.move_to_element(semlist)
        hover.perform()

        item = driver.find_element_by_xpath(
            "//*[@id='semesterSubId']/option[4]")
        try:
            # element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div/div/div/div[3]/div/div/div/section/div/div/div[2]/form/div/div/div[1]/div/div/select")))
            # semlist = driver.find_element_by_xpath("//*[@id='semesterSubId']")
            # semlist.click()
            # hover = action.move_to_element(semlist)
            # hover.perform()

            # item = driver.find_element_by_xpath("//*[@id='semesterSubId']/option[4]")
            try:
                select = Select(semlist)
                selected_option = select.first_selected_option
                print('\n\n\n\n\n\n\n', selected_option.text, '\n\n\n\n\n\n\n')
            except:
                print('\n\n\n\n\n\n\nws\n\n\n\n\n\n\n')
            item.click()
            # viewbutton = driver.find_element_by_xpath("//*[@id='studentTimeTable']/div[2]/div/button")
            # viewbutton.click()

            try:
                newelement = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "timeTableStyle")))
            finally:
                page_source = driver.page_source
        finally:
            TD = []
            page_source = driver.page_source
            print(page_source)
            table = driver.find_elements_by_xpath(
                '//*[@id="studentGradeView"]/div/div/div[3]/div/div/div/table')
            rows = table.find_elements_by_tag_name('tr')
            for row in rows:
                for i in len(rows):
                    col = row.find_elements_by_tag_name('td')[i]
                    TD.append(col.text)
            print(TD)
    return render_template('home.html')


@app.route('/logout')
def logout():
    global driver
    if driver is not None:
        driver.close()
        session.pop('id', None)
        session.pop('timetable', 0)
        session.pop('classes', 0)
        session.pop('cgpa', 0)
        session.pop('gpa', 0)
        session.pop('name', None)
        session.pop('reg', None)
        return render_template('login.html')
    else:
        session.pop('id', None)
        session.pop('timetable', 0)
        session.pop('classes', 0)
        session.pop('cgpa', 0)
        session.pop('gpa', 0)
        session.pop('name', None)
        session.pop('reg', None)
        return render_template('login.html')


# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
