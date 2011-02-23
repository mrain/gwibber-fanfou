import network, util, htmllib, re
import sqlite3
from util import log, exceptions, resources
from util.const import *
from gettext import lgettext as _
log.logger.name = "fanfou"
API_PREFIX = "http://api.fanfou.com"
URL_PREFIX = "http://fanfou.com"
PROTOCOL_INFO = {
	"name": "fanfou",
	"version": "1.0",
	"config": [
		"private:password",
		"username",
		"color",
		"receive_enabled",
		"send_enabled",
	],

	"authtype": "login",
	"color": "#acdae5",

	"features": [
		"send",
		"receive",
		"search"
		"tag",
		"reply",
		"responses",
		"private",
		"public",
		"delete",
		"retweet",
		"like",
		"send_thread",
		"send_private",
		"user_messages",
		"sincetime",
	],

	"default_streams": [
		"receive",
		"responses",
		"private",
	],
}

class Client:
	def __init__(self, acct):
		self.account = acct
		url = "/".join((API_PREFIX, "account/verify_credentials.json"))
		m = network.Download(url, False, False, self.account["username"], self.account["password"]).get_json()
		if not m.has_key("name") or not m.has_key("id"):
			raise exceptions.GwibberServiceError("Unavailable")
		self.account["name"] = m["name"]
		self.account["username"] = m["id"]

	def _common(self, data):
		m = {}
		try:
			m["mid"] = str(data["id"])
			m["service"] = "fanfou"
			m["account"] = self.account["id"]
			m["time"] = util.parsetime(data["created_at"])
			m["text"] = data["text"]
			m["to_me"] = ("@%s" % self.account["name"])
			m["html"] = util.linkify(data["text"],
				((util.PARSE_HASH, '#<a class="hash" href="%s#search?q=\\1">\\1</a>#' % URL_PREFIX),
					(util.PARSE_NICK, '@<a class="nick" href="%s/\\1">\\1</a>' % URL_PREFIX)), escape = False)
			m["content"] = util.linkify(data["text"],
				((util.PARSE_HASH, '#<a class="hash" href="gwibber:/tag?acct=%s&query=\\1">\\1</a>#' % m["account"]),
				(util.PARSE_NICK, '@<a class="nick" href="gwibber:/user?acct=%s&name=\\1">\\1</a>' % m["account"])), escape=False)
			images = util.imagepreview(m["text"])
			if images:
				m["images"] = images
		except:
			log.logger.error("%s failure -'%s'", PROTOCOL_INFO["name"], data)
		return m

	def _user(self, user):
		return {
			"name": user["name"],
			"nick": user["screen_name"],
			"id": user["id"],
			"location": user["location"],
			"followers": user["followers_count"],
			"image": user["profile_image_url"],
			"url": user["url"],
			"is_me": user["id"] == self.account["name"],
		}

	def _message(self, data):
		if type(data) == type(None):
			return []

		m = self._common(data)
		m["source"] = data.get("source", False)

		if "in_reply_to_status_id" in data and data["in_reply_to_status_id"]:
			m["reply"] = {}
			m["reply"]["id"] = data["in_reply_to_status_id"]
			m["reply"]["nick"] = data["in_reply_to_screen_name"]
			m["reply"]["url"] = "/".join((URL_PREFIX, "statuses", str(m["reply"]["id"])))
		m["sender"] = self._user(data["user"] if "user" in data else data["sender"])
		m["url"] = "/".join((URL_PREFIX, "statuses", m["mid"]))

		return m

	def _private(self, data):
		m = self._message(data)
		m["private"] = True

		m["recipient"] = {}
		m["recipient"]["name"] = data["recipient"]["name"]
		m["recipient"]["nick"] = data["recipient"]["screen_name"]
		m["recipient"]["id"] = data["recipient"]["id"]
		m["recipient"]["image"] = data["recipient"]["profile_image_url"]
		m["recipient"]["location"] = data["recipient"]["location"]
		m["recipient"]["url"] = "/".join((URL_PREFIX, m["recipient"]["id"]))
		m["recipient"]["is_me"] = m["recipient"]["id"] == self.account["username"]
		m["to_me"] = m["recipient"]["is_me"]
		return m

	def _get(self, path, parse="message", post=False, single=False, **args):
		url = "/".join((API_PREFIX, path))
		data = network.Download(url, util.compact(args), post, self.account["username"], self.account["password"]).get_json()
		if isinstance(data, dict) and data.get("error", 0):
			if "authenticate" in data["error"]:
				raise exceptions.GwibberServiceError("auth", self.account["service"], self.account["username"], data["error"])
		elif isinstance(data, dict) and data.get("error", 0):
			log.logger.error("%s failure - %s", PROTOCOL_INFO["name"], data["error"])
			return []
		elif isinstance(data, str):
			log.logger.error("%s unexpected result - %s", PROTOCOL_INFO["name"], data)
			return []

		if single: return [getattr(self, "_%s" % parse)(data)]
		if parse: return [getattr(self, "_%s" % parse)(m) for m in data]
		else: return []
	
	def _search(self, **args):
		return self._get("statuses/public_timeline.json", **args)

	def __call__(self, opname, **args):
		return getattr(self, opname)(**args)

	def get_mid_from_time(self, time):
		if time == None:
			return None
		db = sqlite3.connect(SQLITE_DB_FILENAME)
		query = """
				SELECT mid FROM messages
				WHERE account = '%s' AND time='%s'
				""" % (self.account["id"], time)
		return db.execute(query).fetchall()[0][0]

	def receive(self, count=util.COUNT, since=None):
		return self._get("statuses/friends_timeline.json", count=count, since_id=self.get_mid_from_time(since))

	def user_messages(self, id=None, count=util.COUNT, since=None):
		return self._get("statuses/user_timeline.json", id=id, count=count, since_id=since)

	def responses(self, count=util.COUNT, since=None):
		return self._get("statuses/replies.json", count=count, since_id=self.get_mid_from_time(since))

	def private(self, count=util.COUNT, since=None):
		return self._get("direct_messages.json", "private", count=count, since_id=self.get_mid_from_time(since))

	def public(self):
		return self._get("statuses/public_timeline.json")

	def search(self, query, count=util.COUNT, since=None):
		return self._search(q=query, rpp=count, since_id=self.get_mid_from_time(since))

	def tag(self, query, count=util.COUNT, since=None):
		return self._search(q="#%s#" % query, count=count, since_id=self.get_mid_from_time(since))

	def delete(self, message):
		self._get("statuses/destroy/%s.json" % message["mid"], None, post=True, do=1)
		return []

	def like(self, message):
		self._get("favorites/create/%s.json" % message["mid"], None, post=True, do=1)
		return []

	def send(self, message):
		return self._get("statuses/update.json", post=True, single=True,
			status=message, source="gwibber")

	def send_private(self, message, private):
		return self._get("direct_messages/new.json", "private", post=True, single=True,
			text=message, screen_name=private["sender"]["nick"])

	def send_thread(self, message, target):
		return self._get("statuses/update.json", post=True, single=True,
			status=message, source="gwibber", in_reply_to_status_id=target["mid"])

