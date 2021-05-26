import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

chrome_options = webdriver.ChromeOptions() 
chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2}) 
chrome_options.add_argument("--no-sandbox") 
chrome_options.add_argument("--disable-setuid-sandbox") 

chrome_options.add_argument("--remote-debugging-port=9222")  # this
# chrome_options.add_argument("--headless")  # without interface
chrome_options.add_argument("--disable-dev-shm-using") 
chrome_options.add_argument("--disable-extensions") 
chrome_options.add_argument("--disable-gpu") 
chrome_options.add_argument("start-maximized") 
chrome_options.add_argument("disable-infobars")
chrome_options.add_argument(r"user-data-dir=.\cookies\\test") 

driver = webdriver.Chrome('/home/slava/parsing/parsing/lesson8/chromedriver_linux64/chromedriver', chrome_options=chrome_options)
driver.get("https://www.instagram.com/")
time.sleep(2)
elememt = driver.find_element_by_xpath("//input[@name='username']")
elememt.send_keys("79218845458")
elememt = driver.find_element_by_xpath("//input[@name='password']")
elememt.send_keys("slava_123")
button = driver.find_element_by_xpath("//button[@type='submit']")
button.click()
driver.get("https://www.facebook.com/")

for article in driver.find_element_by_tag_name("article"):
    print(article.find_element_by_tag_name("a"))
# time.sleep(10)
# driver.close()
