"""
BidBuddy — 核心引擎
整合爬虫抓取、关键词匹配、AI过滤、数据存储的中央调度器
"""
import logging
import os
import sys
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

# 确保 src 目录在路径中
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from storage import Storage, BidItem
from matcher import KeywordMatcher
from llm_client import LLMClient

logger = logging.getLogger("BidBuddy.Core")


# ─── 网站注册表 ─────────────────────────────────────────────

def get_default_sites() -> Dict[str, Dict]:
    """获取内置招标网站列表"""
    return {
        'chinabidding': {'name': '中国采购与招标网', 'url': 'http://www.chinabidding.cn/'},
        'dlzb': {'name': '中国电力招标网', 'url': 'http://www.dlzb.com/'},
        'chinabiddingcc': {'name': '中国采购招标网', 'url': 'http://www.chinabidding.cc/'},
        'gdtzb': {'name': '国电投招标网', 'url': 'http://www.gdtzb.com'},
        'cpeinet': {'name': '中国电力设备信息网', 'url': 'http://www.cpeinet.com.cn/'},
        'espic': {'name': '电能e招采', 'url': 'https://ebid.espic.com.cn/'},
        'chng': {'name': '华能集团电子商务平台', 'url': 'http://ec.chng.com.cn/ecmall/'},
        'powerchina': {'name': '中国电建采购电子商务平台', 'url': 'http://ec.powerchina.cn'},
        'powerchina_bid': {'name': '中国电建采购招标数智化平台', 'url': 'https://bid.powerchina.cn/bidweb/'},
        'powerchina_ec': {'name': '中国电建设备物资集中采购平台', 'url': 'https://ec.powerchina.cn/'},
        'powerchina_scm': {'name': '中国电建供应链云服务平台', 'url': 'https://scm.powerchina.cn/'},
        'ceec': {'name': '中国能建电子采购平台', 'url': 'https://ec.ceec.net.cn/'},
        'chdtp': {'name': '中国华电电子商务平台', 'url': 'http://www.chdtp.com/'},
        'cdt': {'name': '中国大唐电子商务平台', 'url': 'http://www.cdt-ec.com/'},
        'ebidding': {'name': '国义招标', 'url': 'http://www.ebidding.com/portal/'},
        'neep': {'name': '国家能源e购', 'url': 'https://www.neep.shop/'},
        'ceic': {'name': '国家能源集团生态协作平台', 'url': 'https://cooperation.ceic.com/'},
        'sgcc': {'name': '国家电网电子商务平台', 'url': 'https://ecp.sgcc.com.cn/'},
        'cecep': {'name': '中国节能环保电子采购平台', 'url': 'http://www.ebidding.cecep.cn/'},
        'gdg': {'name': '广州发展集团电子采购平台', 'url': 'https://eps.gdg.com.cn/'},
        'crpower': {'name': '华润电力', 'url': 'https://b2b.crpower.com.cn'},
        'crc': {'name': '华润集团守正电子招标采购平台', 'url': 'https://szecp.crc.com.cn/'},
        'cgnpc': {'name': '中广核电子商务平台', 'url': 'https://ecp.cgnpc.com.cn'},
        'dongfang': {'name': '东方电气', 'url': 'http://nsrm.dongfang.com/'},
        'zjycgzx': {'name': '浙江云采购中心', 'url': 'https://www.zjycgzx.com'},
        'ctg': {'name': '中国三峡电子采购平台', 'url': 'https://eps.ctg.com.cn/'},
        'sdicc': {'name': '国投集团电子采购平台', 'url': 'https://www.sdicc.com.cn/'},
        'csg': {'name': '中国南方电网供应链服务平台', 'url': 'http://www.bidding.csg.cn/'},
        'sgccetp': {'name': '国网电子商务平台电工交易专区', 'url': 'https://sgccetp.com.cn/'},
        'powerbeijing': {'name': '北京京能电子商务平台', 'url': 'http://www.powerbeijing-ec.com'},
        'ccccltd': {'name': '中交集团供应链管理系统', 'url': 'http://ec.ccccltd.cn/'},
        'jchc': {'name': '江苏交通控股', 'url': 'https://zbcg.jchc.cn/portal'},
        'minmetals': {'name': '中国五矿集团供应链管理平台', 'url': 'https://ec.minmetals.com.cn/'},
        'cnbm': {'name': '中国建材集团采购平台', 'url': 'https://c.cnbm.com.cn/'},
        'xcmg': {'name': '徐工全球数字化供应链系统平台', 'url': 'http://xdsc.xcmg.com:8985/'},
        'xinecai': {'name': '安天智采', 'url': 'http://www.xinecai.com'},
        'faw': {'name': '中国一汽电子招标采购交易平台', 'url': 'https://srm.etp.faw.cn/staging'},
    }


class Engine:
    """BidBuddy 核心引擎"""

    def __init__(self, log_callback: Callable = None):
        self.log = log_callback or (lambda x: logger.info(x))
        self.storage = Storage()
        self._crawlers: List = []
        self._stop_event = threading.Event()

        # 当前配置
        self.config: Dict[str, Any] = {
            'keywords': '',
            'exclude': '',
            'must_contain': '',
            'interval': 20,
            'enabled_sites': list(get_default_sites().keys()),
            'use_selenium': False,
            'ai_enabled': False,
            'ai_model': 'deepseek-chat',
            'ai_key': '',
            'ai_custom_url': '',
        }

        # 进度追踪
        self.progress_current = 0
        self.progress_total = 0
        self.progress_site = ""

    def _init_crawlers(self) -> List:
        """初始化爬虫列表"""
        crawlers = []
        enabled = self.config.get('enabled_sites', [])
        default_sites = get_default_sites()
        use_selenium = self.config.get('use_selenium', False)

        # 专用爬虫类
        try:
            from crawler.chinabidding import ChinaBiddingCrawler
            if 'chinabidding' in enabled:
                crawlers.append(ChinaBiddingCrawler({
                    'search_keywords': self._keywords()[:3]
                }))
        except ImportError:
            pass

        # 通用爬虫（覆盖大部分网站）
        from crawler.custom import CustomCrawler

        if use_selenium:
            try:
                from crawler.selenium_crawler import SeleniumCrawler, SELENIUM_AVAILABLE
                if SELENIUM_AVAILABLE:
                    crawler_cls = lambda cfg, name, url: SeleniumCrawler(cfg, name, url, headless=True)
                else:
                    self.log("⚠️ Selenium不可用，回退到普通模式")
                    use_selenium = False
                    crawler_cls = lambda cfg, name, url: CustomCrawler(cfg, name, url)
            except ImportError:
                self.log("⚠️ Selenium未安装，使用普通模式")
                use_selenium = False
                crawler_cls = lambda cfg, name, url: CustomCrawler(cfg, name, url)
        else:
            crawler_cls = lambda cfg, name, url: CustomCrawler(cfg, name, url)

        for key in enabled:
            if key in default_sites and key != 'chinabidding':
                site = default_sites[key]
                try:
                    crawlers.append(crawler_cls({}, site['name'], site['url']))
                except Exception as e:
                    self.log(f"⚠️ 加载失败 {site['name']}: {e}")

        self.log(f"📡 已加载 {len(crawlers)} 个网站爬虫")
        return crawlers

    def _keywords(self) -> List[str]:
        return [k.strip() for k in self.config.get('keywords', '').split(',') if k.strip()]

    def _exclude_words(self) -> List[str]:
        return [k.strip() for k in self.config.get('exclude', '').split(',') if k.strip()]

    def _must_words(self) -> List[str]:
        return [k.strip() for k in self.config.get('must_contain', '').split(',') if k.strip()]

    def _get_llm(self) -> Optional[LLMClient]:
        """获取LLM客户端"""
        if not self.config.get('ai_enabled'):
            return None
        key = self.config.get('ai_key', '')
        if not key:
            return None
        return LLMClient(
            model_id=self.config.get('ai_model', 'deepseek-chat'),
            api_key=key,
            custom_url=self.config.get('ai_custom_url', ''),
            log_callback=self.log,
        )

    def parse_intent(self, user_input: str) -> Dict:
        """解析用户自然语言意图"""
        llm = self._get_llm()
        if llm:
            result = llm.parse_intent(user_input)
            self.log(f"🧠 意图解析：{result.get('summary', '')}")
            return result
        # 无AI时，直接用输入作为关键词
        return {
            "keywords": user_input,
            "exclude": "",
            "must_contain": "",
            "schedule": "immediate",
            "summary": f"直接搜索：{user_input[:30]}",
        }

    def run_once(self, keywords: str = "", exclude: str = "", must_contain: str = "",
                 progress_cb: Callable = None) -> Dict:
        """
        执行一次完整的招投标检索

        Args:
            keywords: 搜索关键词（逗号分隔）
            exclude: 排除关键词
            must_contain: 必须包含关键词
            progress_cb: 进度回调 (current, total, site_name)

        Returns:
            结果摘要字典
        """
        self._stop_event.clear()

        # 使用传入参数或配置
        if keywords:
            self.config['keywords'] = keywords
        if exclude:
            self.config['exclude'] = exclude
        if must_contain:
            self.config['must_contain'] = must_contain

        kw_list = self._keywords()
        if not kw_list:
            self.log("⚠️ 未设置搜索关键词")
            return {'new_count': 0, 'total': 0}

        self.log("=" * 50)
        self.log(f"🔍 开始检索：{', '.join(kw_list[:5])}")
        self.log(f"📡 目标网站：{len(self.config.get('enabled_sites', []))} 个")

        # 初始化爬虫和匹配器
        self._crawlers = self._init_crawlers()
        matcher = KeywordMatcher(
            include_keywords=kw_list,
            exclude_keywords=self._exclude_words(),
            must_contain_keywords=self._must_words()
        )
        llm = self._get_llm()

        total_crawlers = len(self._crawlers)
        self.progress_total = total_crawlers
        self.progress_current = 0

        all_matched = []
        ai_approved = 0
        ai_rejected = 0

        for idx, crawler in enumerate(self._crawlers, 1):
            if self._stop_event.is_set():
                self.log("⏹️ 检索被中断")
                break

            self.progress_current = idx
            self.progress_site = crawler.name
            if progress_cb:
                progress_cb(idx, total_crawlers, crawler.name)

            try:
                self.log(f"  [{idx}/{total_crawlers}] 爬取 {crawler.name}...")
                bids = crawler.crawl(stop_event=self._stop_event)

                if bids is None:
                    self.log(f"  ❌ {crawler.name} 爬取失败")
                    continue

                matched_count = 0
                for bid in bids:
                    if self._stop_event.is_set():
                        break

                    result = matcher.match_any(bid.title, getattr(bid, 'content', ''))

                    if result.matched:
                        # AI 二次过滤
                        if llm and self.config.get('ai_enabled'):
                            ai_result = llm.filter_bid(
                                bid.title,
                                getattr(bid, 'content', ''),
                                keywords=self.config.get('keywords', ''),
                            )
                            if not ai_result.get('relevant', True):
                                ai_rejected += 1
                                continue
                            ai_approved += 1

                        # 去重保存
                        bid_item = BidItem(
                            title=bid.title,
                            url=bid.url if hasattr(bid, 'url') else '',
                            source=crawler.name,
                            content=getattr(bid, 'content', ''),
                            publish_date=getattr(bid, 'publish_date', None),
                        )
                        if not self.storage.exists(bid_item):
                            self.storage.save(bid_item)
                            all_matched.append(bid_item)
                            matched_count += 1

                self.log(f"  ✅ {crawler.name}：{len(bids)}条，匹配 {matched_count}条")

            except Exception as e:
                self.log(f"  ❌ {crawler.name} 异常：{str(e)[:80]}")

        # 汇总
        total_all = self.storage.count_all()
        self.log(f"\n📊 本轮完成：新增 {len(all_matched)} 条，数据库共 {total_all} 条")
        if llm and self.config.get('ai_enabled'):
            self.log(f"🤖 AI过滤：通过 {ai_approved} 条，拒绝 {ai_rejected} 条")

        # 清理
        try:
            from crawler.selenium_crawler import SharedBrowserManager
            SharedBrowserManager.close()
        except Exception:
            pass

        return {
            'new_count': len(all_matched),
            'total': total_all,
            'sites_crawled': total_crawlers,
            'ai_approved': ai_approved,
            'ai_rejected': ai_rejected,
        }

    def stop(self):
        """中断当前检索"""
        self._stop_event.set()
        self.log("⏹️ 发送停止信号...")
