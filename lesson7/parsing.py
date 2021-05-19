import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

chromeOptions = webdriver.ChromeOptions() 
chromeOptions.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2}) 
chromeOptions.add_argument("--no-sandbox") 
chromeOptions.add_argument("--disable-setuid-sandbox") 

chromeOptions.add_argument("--remote-debugging-port=9222")  # this

chromeOptions.add_argument("--disable-dev-shm-using") 
chromeOptions.add_argument("--disable-extensions") 
chromeOptions.add_argument("--disable-gpu") 
chromeOptions.add_argument("start-maximized") 
chromeOptions.add_argument("disable-infobars")
chromeOptions.add_argument(r"user-data-dir=.\cookies\\test") 

driver = webdriver.Chrome('/home/slava/parsing/parsing/lesson8/chromedriver_linux64/chromedriver', chrome_options=chromeOptions)
driver.get("https://www.instagram.com/")
time.sleep(2)
elememt = driver.find_element_by_xpath("//input[@name='username']")
elememt.send_keys("user")
elememt = driver.find_element_by_xpath("//input[@name='password']")
elememt.send_keys("password")
button = driver.find_element_by_xpath("//button[@type='submit']")
elememt.click()


# time.sleep(10)
# driver.close()
