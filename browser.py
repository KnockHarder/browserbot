from DrissionPage import ChromiumPage
from requests import Session


class TabInfo:
    def __init__(self, id: str, url: str, title: str):
        self.id = id
        self.url = url
        self.title = title


class Browser:
    def __init__(self):
        self.page = ChromiumPage()
        self.session = Session()

    def chrome_targets(self):
        agent = self.page
        return self.session.get(f'http://{agent.address}/json').json()

    @property
    def tabs(self) -> list[TabInfo]:
        return [TabInfo(tab['id'], tab['url'], tab['title'])
                for tab in filter(lambda x: x['type'] == 'page', self.chrome_targets())]

    def switch_to_tab(self, tab_id):
        self.page.to_tab(tab_id)

    def all_tab_with_prefix(self, url_prefix) -> list[TabInfo]:
        return [x for x in self.tabs if x.url.startswith(url_prefix)]

    def to_tab(self, tab: TabInfo = None, tab_id: str = None):
        if tab:
            tab_id = tab.id
        self.page.to_tab(tab_id)

    def is_tab_alive(self, tab: TabInfo):
        return tab in [x.id for x in self.tabs]


if __name__ == '__main__':
    def main():
        page = ChromiumPage()
        page.to_tab()
        page.to_main_tab()
