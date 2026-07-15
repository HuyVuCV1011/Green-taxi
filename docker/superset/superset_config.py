import os


SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_METADATA_DATABASE_URI"]

WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False
ENABLE_PROXY_FIX = False

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "ENABLE_TEMPLATE_PROCESSING": False,
}

# Force one coherent light enterprise theme. With THEME_DARK enabled Superset
# follows the operating-system preference, which can turn chart labels white
# even when a dashboard intentionally uses white cards.
THEME_DEFAULT = {
    "algorithm": "default",
    "token": {
        "brandAppName": "Green Taxi Analytics",
        "brandLogoAlt": "Green Taxi Analytics",
        "brandLogoUrl": "/static/assets/images/superset-logo-horiz.png",
        "brandLogoHref": "/",
        "brandLogoHeight": "24px",
        "brandLogoMargin": "18px 0",
        "brandIconMaxWidth": 120,
        "brandSpinnerUrl": None,
        "brandSpinnerSvg": None,
        "fontUrls": [],
        "colorPrimary": "#0F6CBD",
        "colorLink": "#0F6CBD",
        "colorInfo": "#0F6CBD",
        "colorSuccess": "#107C10",
        "colorWarning": "#FFB900",
        "colorError": "#D13438",
        "colorBgLayout": "#F4F7FB",
        "colorBgContainer": "#FFFFFF",
        "colorText": "#24364B",
        "colorTextSecondary": "#5B6B7F",
        "colorBorder": "#DFE7F0",
        "borderRadius": 8,
        "fontFamily": "Segoe UI, Inter, Helvetica, Arial, sans-serif",
        "fontWeightStrong": "600",
    },
    "echartsOptionsOverrides": {
        "backgroundColor": "transparent",
        "color": [
            "#0F6CBD",
            "#2AA198",
            "#6B69D6",
            "#F2C811",
            "#D83B01",
            "#107C10",
            "#C239B3",
        ],
        "textStyle": {
            "color": "#40566D",
            "fontFamily": "Segoe UI, Inter, Helvetica, Arial, sans-serif",
        },
        "legend": {"textStyle": {"color": "#40566D", "fontSize": 11}},
        "xAxis": {
            "axisLabel": {"color": "#5B6B7F", "fontSize": 11},
            "axisLine": {"lineStyle": {"color": "#C9D5E2"}},
            "splitLine": {"lineStyle": {"color": "#EDF1F6"}},
        },
        "yAxis": {
            "axisLabel": {"color": "#5B6B7F", "fontSize": 11},
            "axisLine": {"lineStyle": {"color": "#C9D5E2"}},
            "splitLine": {"lineStyle": {"color": "#EDF1F6"}},
        },
        "tooltip": {
            "backgroundColor": "rgba(255,255,255,0.98)",
            "borderColor": "#C9D5E2",
            "textStyle": {"color": "#24364B"},
        },
    },
}
THEME_DARK = None

ROW_LIMIT = 50000
SQL_MAX_ROW = 100000
SUPERSET_WEBSERVER_TIMEOUT = 120

LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
    "vi": {"flag": "vn", "name": "Vietnamese"},
}
BABEL_DEFAULT_LOCALE = "en"
