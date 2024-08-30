import argparse
import random
import re
import socket
import threading
import urllib.request
import os
from time import time, sleep

import socks

# Color constants
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

user_agents = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.94 Chrome/37.0.2062.94 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/600.8.9 (KHTML, like Gecko) Version/8.0.8 Safari/600.8.9",
    "Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4",
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
]

try:
    with open("user_agents.txt", "r") as f:
        user_agents.extend(line.strip() for line in f)
except FileNotFoundError:
    pass

class Proxy:
    def __init__(self, method, proxy):
        if method.lower() not in ["http", "https", "socks4", "socks5"]:
            raise NotImplementedError("Only HTTP, HTTPS, SOCKS4, and SOCKS5 are supported")
        self.method = method.lower()
        self.proxy = proxy

    def is_valid(self):
        return re.match(r"\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?$", self.proxy)

    def check_http_https(self, site, timeout, user_agent, verbose):
        url = f"{self.method}://{self.proxy}"
        proxy_support = urllib.request.ProxyHandler({self.method: url})
        opener = urllib.request.build_opener(proxy_support)
        urllib.request.install_opener(opener)
        req = urllib.request.Request(f"{self.method}://{site}")
        req.add_header("User-Agent", user_agent)
        try:
            start_time = time()
            urllib.request.urlopen(req, timeout=timeout)
            end_time = time()
            time_taken = end_time - start_time
            verbose_print(verbose, f"{GREEN}Proxy {self.proxy} is valid, time taken: {time_taken}{RESET}")
            return True, time_taken, None
        except Exception as e:
            verbose_print(verbose, f"{RED}Proxy {self.proxy} is not valid, error: {str(e)}{RESET}")
            return False, 0, e

    def check_socks(self, site, timeout, verbose):
        protocol = socks.SOCKS4 if self.method == "socks4" else socks.SOCKS5
        socks.set_default_proxy(protocol, self.proxy.split(':')[0], int(self.proxy.split(':')[1]))
        socket.socket = socks.socksocket
        try:
            start_time = time()
            urllib.request.urlopen(site, timeout=timeout)
            end_time = time()
            time_taken = end_time - start_time
            verbose_print(verbose, f"{GREEN}Proxy {self.proxy} is valid, time taken: {time_taken}{RESET}")
            return True, time_taken, None
        except Exception as e:
            verbose_print(verbose, f"{RED}Proxy {self.proxy} is not valid, error: {str(e)}{RESET}")
            return False, 0, e

    def check(self, site, timeout, user_agent, verbose):
        if self.method in ["http", "https"]:
            return self.check_http_https(site, timeout, user_agent, verbose)
        elif self.method in ["socks4", "socks5"]:
            return self.check_socks(site, timeout, verbose)
        else:
            raise NotImplementedError(f"Proxy method {self.method} is not supported")

    def __str__(self):
        return self.proxy

def verbose_print(verbose, message):
    if verbose:
        print(message)

def check(file, timeout, method, site, verbose, random_user_agent):
    proxies = []
    with open(file, "r") as f:
        proxies = [Proxy(method, line.strip()) for line in f]

    print(f"{BLUE}Checking {len(proxies)} proxies{RESET}")
    proxies = filter(lambda x: x.is_valid(), proxies)
    valid_proxies = []
    user_agent = random.choice(user_agents)

    def check_proxy(proxy):
        new_user_agent = user_agent if not random_user_agent else random.choice(user_agents)
        valid, time_taken, error = proxy.check(site, timeout, new_user_agent, verbose)
        if valid:
            valid_proxies.append(proxy)

    threads = [threading.Thread(target=check_proxy, args=(proxy,)) for proxy in proxies]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    with open(file, "w") as f:
        for proxy in valid_proxies:
            f.write(f"{proxy}\n")

    print(f"{GREEN}Found {len(valid_proxies)} valid proxies{RESET}")

def add_proxies_to_proxychains(proxy_file, proxychains_conf='/etc/proxychains4.conf', protocol='http'):
    if not os.path.exists(proxychains_conf):
        print(f"{RED}Error: {proxychains_conf} does not exist.{RESET}")
        return

    if not os.path.exists(proxy_file):
        print(f"{RED}Error: {proxy_file} does not exist.{RESET}")
        return

    # Ensure the protocol is one of the accepted types
    if protocol not in ['http', 'https', 'socks4', 'socks5']:
        print(f"{RED}Error: Invalid protocol specified. Use 'http', 'https', 'socks4', or 'socks5'.{RESET}")
        return

    # Prepare the necessary lines for the configuration
    header_lines = [
        "dynamic_chain",
        "proxy_dns",
        "log_level debug",
        "remote_dns_subnet 224",
        "tcp_read_time_out 15000",
        "tcp_connect_time_out 8000",
        "[ProxyList]"
    ]
    
    # Add Tor proxies first
    new_proxies = [
        "socks5 127.0.0.1 9050"
    ]

    # Add new proxies from the provided file
    with open(proxy_file, "r") as f:
        for proxy in f:
            proxy = proxy.strip()
            if proxy and ':' in proxy:
                ip, port = proxy.split(":", 1)
                proxy_entry = f"{protocol} {ip} {port}"
                new_proxies.append(proxy_entry)

    # Write updated configuration
    with open(proxychains_conf, "w") as conf:
        # Write the header lines
        for line in header_lines:
            conf.write(line + "\n")

        # Write new proxies, including Tor proxies first
        for proxy in new_proxies:
            conf.write(f"{proxy}\n")

    print(f"{GREEN}Proxies from {proxy_file} have been added to {proxychains_conf}.{RESET}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="Dismiss the proxy after -t seconds",
        default=20,
    )
    parser.add_argument("-p", "--proxy", help="Check HTTPS, HTTP, SOCKS4, or SOCKS5 proxies", default="http")
    parser.add_argument("-l", "--list", help="Path to your proxy list file", default="output.txt")
    parser.add_argument(
        "-s",
        "--site",
        help="Check with specific website like google.com",
        default="https://google.com/",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Increase output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--random_agent",
        help="Use a random user agent per proxy",
        action="store_true",
    )
    parser.add_argument(
        "--add_to_proxychains",
        help="Add proxies to proxychains.conf",
        action="store_true",
    )
    parser.add_argument(
        "--proxychains_conf",
        help="Path to your proxychains.conf file",
        default="/etc/proxychains4.conf",
    )
    parser.add_argument(
        "--cycle",
        type=int,
        help="Repeat the proxy check and addition every X seconds",
        default=None,
    )
    args = parser.parse_args()

    def run_cycle():
        check(file=args.list, timeout=args.timeout, method=args.proxy, site=args.site, verbose=args.verbose,
              random_user_agent=args.random_agent)

        if args.add_to_proxychains:
            add_proxies_to_proxychains(proxy_file=args.list, proxychains_conf=args.proxychains_conf, protocol=args.proxy)

    if args.cycle:
        while True:
            run_cycle()
            print(f"{YELLOW}Cycling in {args.cycle} seconds...{RESET}")
            sleep(args.cycle)
    else:
        run_cycle()

if __name__ == "__main__":
    main()
