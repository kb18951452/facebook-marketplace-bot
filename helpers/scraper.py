import os
import json
import pickle
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidArgumentException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import logging

logger = logging.getLogger(__name__)


class Scraper:
	# This time is used when we are waiting for element to get loaded in the html
	wait_element_time = 30

	# In this folder we will save cookies from logged in users
	cookies_folder = 'cookies' + os.path.sep

	def __init__(self, url):
		self.url = url

		self.setup_driver_options()
		self.setup_driver()

	# Automatically close driver on destruction of the object
	def __del__(self):
		try:
			self.driver.quit()
		except Exception:
			pass

	# Add these options in order to make chrome driver appear as a human instead of detecting it as a bot
	# Also change the 'cdc_' string in the chromedriver.exe with Notepad++ for example with 'abc_' to prevent detecting it as a bot
	def setup_driver_options(self):

		self.driver_options = Options()

		arguments = [
			'--disable-blink-features=AutomationControlled',
			'--window-size=1920,1080',
			'--log-level=3',
		]

		# Headless by default (scheduled/unattended runs). Set FB_BOT_HEADLESS=0
		# to open a real visible window — needed for the tier-3 manual-login
		# fallback in add_login_functionality(), which requires a human to
		# actually see and click through the browser.
		if os.environ.get('FB_BOT_HEADLESS', '1').lower() not in ('0', 'false', 'no'):
			arguments.insert(1, '--headless=new')

		experimental_options = {
			'excludeSwitches': ['enable-automation', 'enable-logging'],
			'prefs': {'profile.default_content_setting_values.notifications': 2}
		}

		for argument in arguments:
			self.driver_options.add_argument(argument)

		for key, value in experimental_options.items():
			self.driver_options.add_experimental_option(key, value)

	# Setup chrome driver with predefined options
	def setup_driver(self):
		# Force Google Chrome (not Chromium) and win64 to get the correct exe
		chrome_driver_path = ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install()

		# Optional: print to verify it's ending with chromedriver.exe (not THIRD_PARTY_NOTICES...)
		print(f"ChromeDriver path: {chrome_driver_path}")

		self.driver = webdriver.Chrome(service=ChromeService(chrome_driver_path), options=self.driver_options)
		self.driver.get(self.url)
		self.driver.maximize_window()

	# Add login functionality. Tries, in order: saved cookies → automated
	# credential login (handles the "re-enter your password" screen) → manual.
	def add_login_functionality(self, login_url, is_logged_in_selector, cookies_file_name):
		self.login_url = login_url
		self.is_logged_in_selector = is_logged_in_selector
		self.cookies_file_name = cookies_file_name + '.pkl'
		self.cookies_file_path = self.cookies_folder + self.cookies_file_name

		# 1) Try saved cookies
		if self.is_cookie_file():
			self.load_cookies()
			if self.is_logged_in(8):
				print('Logged in via saved cookies.')
				return
			print('Saved cookies did not yield a logged-in session.')

		# 2) Try automated login with stored credentials
		if self.login_with_credentials():
			self.save_cookies()
			print('Logged in via stored credentials; cookies refreshed.')
			return

		# 3) Manual fallback — the browser is already on the login/challenge page
		print('Automated login did not complete. Please log in manually in the '
		      'browser within 5 minutes (e.g. to clear a 2FA/checkpoint). The '
		      'program will exit if you do not.')
		if not self.is_logged_in(300):
			print('ERROR: Not logged in after the manual window. Exiting.')
			exit()
		self.save_cookies()

	# Load Facebook credentials from env vars first, then credentials.json
	def _load_credentials(self):
		email = os.environ.get('FB_EMAIL')
		password = os.environ.get('FB_PASSWORD')
		if email and password:
			return email, password

		cred_path = 'credentials.json'
		if os.path.exists(cred_path):
			try:
				with open(cred_path) as f:
					data = json.load(f)
				return email or data.get('email'), password or data.get('password')
			except Exception as e:
				print(f'WARNING: Could not read credentials.json: {e}')
		return email, password

	# Return the first element matching any of the given CSS selectors, else None
	def _find_first(self, selectors, wait_element_time=3):
		for selector in selectors:
			element = self.find_element(selector, False, wait_element_time)
			if element:
				return element
		return None

	# Attempt an automated login with stored credentials. Handles both the full
	# login form (email + password) and the password-only re-auth screen.
	def login_with_credentials(self):
		email, password = self._load_credentials()
		if not password:
			print('No stored Facebook password found (set FB_PASSWORD or '
			      'credentials.json) — skipping automated login.')
			return False

		# Land on the login page (a logged-in session redirects to the feed)
		self.driver.get('https://www.facebook.com/login/')
		self.wait_random_time()
		if self.is_logged_in(5):
			return True

		password_field = self._find_first(
			['input#pass', 'input[name="pass"]', 'input[type="password"]'],
			wait_element_time=10,
		)
		if not password_field:
			print('Could not locate the Facebook password field.')
			return False

		# Fill the email/username only if the field is present and empty. On the
		# "re-enter your password" screen there is no email field at all.
		if email:
			email_field = self._find_first(
				['input#email', 'input[name="email"]', 'input[type="email"]'],
				wait_element_time=2,
			)
			if email_field:
				try:
					if not email_field.get_attribute('value'):
						email_field.clear()
						email_field.send_keys(email)
						self.wait_random_time()
				except Exception:
					pass

		try:
			password_field.clear()
		except Exception:
			pass
		password_field.send_keys(password)
		self.wait_random_time()
		password_field.send_keys(Keys.RETURN)

		return self._finalize_login()

	# Poll after submitting credentials: succeed as soon as the logged-in marker
	# appears, clicking through any "save this browser" interstitial. Many extra
	# screens (trusted-device approval, save-browser) auto-resolve, so we keep
	# waiting for the logged-in state rather than abandoning on first sight of a
	# challenge-looking URL. Only after the full timeout do we report a real
	# blocking step and hand off to the manual fallback.
	def _finalize_login(self, timeout=90):
		deadline = time.time() + timeout
		challenge_noted = False
		while time.time() < deadline:
			if self.is_logged_in(2):
				return True
			self._accept_save_browser_prompt()
			if not challenge_noted and self._login_challenge_detected():
				print(f'Note: Facebook showed an extra step ({self.driver.current_url}) '
				      '— waiting to see if it resolves automatically...')
				challenge_noted = True
			time.sleep(2)
		if self._login_challenge_detected():
			print('Facebook is requesting a verification step (2FA/checkpoint) '
			      'that could not be completed automatically.')
		return bool(self.is_logged_in(2))

	# Click through the optional "Remember/Save this browser" interstitial
	def _accept_save_browser_prompt(self):
		xpaths = [
			"//div[@aria-label='Continue'][@role='button']",
			"//div[@aria-label='Save'][@role='button']",
			"//button[@name='login']",
			"//div[@role='button'][contains(., 'Continue')]",
			"//div[@role='button'][contains(., 'Save')]",
		]
		for xpath in xpaths:
			element = self.find_element_by_xpath(xpath, False, 1)
			if element:
				try:
					element.click()
					self.wait_random_time()
					return
				except Exception:
					continue

	# Detect verification steps that require human input (2FA, security checkpoint)
	def _login_challenge_detected(self):
		url = self.driver.current_url.lower()
		return any(token in url for token in ('checkpoint', 'two_step', 'two-step', '/2fac'))

	# Check if cookie file exists
	def is_cookie_file(self):
		return os.path.exists(self.cookies_file_path)

	# Load cookies from file
	def load_cookies(self):
		# Load cookies from the file
		cookies_file = open(self.cookies_file_path, 'rb')
		cookies = pickle.load(cookies_file)

		for cookie in cookies:
			self.driver.add_cookie(cookie)

		cookies_file.close()

		self.go_to_page(self.url)

	# Save cookies to file
	def save_cookies(self):
		# Do not save cookies if there is no cookies_file name
		if not hasattr(self, 'cookies_file_path'):
			return

		# Create folder for cookies if there is no folder in the project
		if not os.path.exists(self.cookies_folder):
			os.mkdir(self.cookies_folder)

		# Open or create cookies file
		cookies_file = open(self.cookies_file_path, 'wb')

		# Get current cookies from the driver
		cookies = self.driver.get_cookies()

		# Save cookies in the cookie file as a byte stream
		pickle.dump(cookies, cookies_file)

		cookies_file.close()

	# Check if user is logged in based on a html element that is visible only for logged in users
	def is_logged_in(self, wait_element_time = None):
		if wait_element_time is None:
			wait_element_time = self.wait_element_time

		return self.find_element(self.is_logged_in_selector, False, wait_element_time)

	# Wait random amount of seconds before taking some action so the server won't be able to tell if you are a bot
	def wait_random_time(self):
		random_sleep_seconds = round(random.uniform(1.20, 2.20), 2)

		time.sleep(random_sleep_seconds)

	# Goes to a given page and waits random time before that to prevent detection as a bot
	def go_to_page(self, page):
		# Wait random time before refreshing the page to prevent the detection as a bot
		self.wait_random_time()

		# Refresh the site url with the loaded cookies so the user will be logged in
		self.driver.get(page)

	def find_element(self, selector, exit_on_missing_element=True, wait_element_time=None):
		if wait_element_time is None:
			wait_element_time = self.wait_element_time

		# Intialize the condition to wait
		wait_until = EC.element_to_be_clickable((By.CSS_SELECTOR, selector))

		try:
			# Wait for element to load
			element = WebDriverWait(self.driver, wait_element_time).until(wait_until)
		except Exception:
			if exit_on_missing_element:
				raise RuntimeError('Timed out waiting for element with css selector "' + selector + '"')
			else:
				return False

		return element

	def find_element_by_xpath(self, xpath, exit_on_missing_element = True, wait_element_time=None):
		if wait_element_time is None:
			wait_element_time = self.wait_element_time

		# Intialize the condition to wait
		wait_until = EC.element_to_be_clickable((By.XPATH, xpath))

		try:
			# Wait for element to load
			element = WebDriverWait(self.driver, wait_element_time).until(wait_until)
		except Exception:
			if exit_on_missing_element:
				raise RuntimeError('Timed out waiting for element with xpath "' + xpath + '"')
			else:
				return False

		return element

	# Wait random time before clicking on the element
	def element_click(self, selector, delay=True):
		if delay:
			self.wait_random_time()

		element = self.find_element(selector)

		try:
			element.click()
		except ElementClickInterceptedException:
			self.driver.execute_script("arguments[0].click();", element)

	# Wait random time before clicking on the element
	def element_click_by_xpath(self, xpath, delay=True):
		if delay:
			self.wait_random_time()

		element = self.find_element_by_xpath(xpath)

		try:
			element.click()
		except ElementClickInterceptedException:
			self.driver.execute_script("arguments[0].click();", element)

	# Wait random time before sending the keys to the element
	def element_send_keys(self, selector, text, delay = True):
		if delay:
			self.wait_random_time()

		element = self.find_element(selector)

		try:
			element.click()
		except ElementClickInterceptedException:
			self.driver.execute_script("arguments[0].click();", element)

		element.send_keys(text)

	# Wait random time before sending the keys to the element
	def element_send_keys_by_xpath(self, xpath, text, delay = True):
		if delay:
			self.wait_random_time()

		element = self.find_element_by_xpath(xpath)

		try:
			element.click()
		except ElementClickInterceptedException:
			self.driver.execute_script("arguments[0].click();", element)

		element.send_keys(text)

	def input_file_add_files(self, selector, files):
		# Normalize: accept either a list of paths or a newline-joined string
		if isinstance(files, list):
			files = '\n'.join(files)

		# Intialize the condition to wait
		wait_until = EC.presence_of_element_located((By.CSS_SELECTOR, selector))

		try:
			# Wait for input_file to load
			input_file = WebDriverWait(self.driver, self.wait_element_time).until(wait_until)
		except Exception:
			raise RuntimeError('Timed out waiting for file input with selector "' + selector + '"')

		self.wait_random_time()

		try:
			input_file.send_keys(files)
		except InvalidArgumentException:
			raise RuntimeError('Invalid file paths for image upload:\n' + files)

	# Wait random time before clearing the element
	def element_clear(self, selector, delay = True):
		if delay:
			self.wait_random_time()

		element = self.find_element(selector)

		element.clear()

	def element_delete_text(self, selector, delay = True):
		if delay:
			self.wait_random_time()

		element = self.find_element(selector)

		# Select all of the text in the input
		element.send_keys(Keys.LEFT_SHIFT + Keys.HOME)
		# Remove the selected text with backspace
		element.send_keys(Keys.BACK_SPACE)

	def element_wait_to_be_invisible(self, selector):
		wait_until = EC.invisibility_of_element_located((By.CSS_SELECTOR, selector))

		try:
			WebDriverWait(self.driver, self.wait_element_time).until(wait_until)
		except Exception:
			logger.warning('Timed out waiting for element to be invisible: ' + selector)

	def element_wait_to_be_present(self, selector, selector_type=By.CSS_SELECTOR):
		wait_until = EC.presence_of_element_located((selector_type, selector))

		try:
			WebDriverWait(self.driver, self.wait_element_time).until(wait_until)
		except TimeoutException:
			raise RuntimeError(f'Timed out waiting for element with selector "{selector}"')
		except Exception as e:
			raise RuntimeError(f'Unexpected error waiting for element with selector "{selector}"') from e

	def scroll_to_element(self, selector):
		element = self.find_element(selector)

		self.driver.execute_script('arguments[0].scrollIntoView(true);', element)

	def scroll_to_element_by_xpath(self, xpath):
		element = self.find_element_by_xpath(xpath)

		self.driver.execute_script('arguments[0].scrollIntoView(true);', element)