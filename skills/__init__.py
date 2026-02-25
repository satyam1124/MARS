"""
skills — MARS skill modules package.

Each sub-module implements a focused capability that MARS can invoke in
response to natural-language commands.  Every public function returns a
``str`` that MARS speaks aloud to the user.

Available modules
-----------------
system_control  : macOS system operations (volume, brightness, sleep, etc.)
web_search      : DuckDuckGo / Wikipedia / URL browsing
weather         : Current conditions and forecast via OpenWeatherMap
news            : Top headlines and topic search via News API
email_manager   : Send and read Gmail messages
calculator      : Math evaluation, unit conversion, currency conversion
translator      : Text translation and language detection via googletrans
"""
