import gtk
from gtk import Builder
import gwibber.microblog

class AccountWidget(gtk.VBox):
	"""AccountWidget: A widget that provides a user interface for configuring identica accounts in Gwibber
	"""

	def __init__(self, account=None, dialog=None):
		"""Creates the account pane for configuring identica accounts"""
		gtk.VBox.__init__( self, False, 20 )
		self.ui = gtk.Builder()
		self.ui.set_translation_domain ("gwibber")
		self.ui.add_from_file (gwibber.resources.get_ui_asset("gwibber-accounts-fanfou.ui"))
		self.ui.connect_signals(self)
		self.vbox_settings = self.ui.get_object("vbox_settings")
		self.pack_start(self.vbox_settings, False, False)
		self.show_all()
		if dialog:
			 dialog.get_object("vbox_create").show()

