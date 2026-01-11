import subprocess
import concurrent.futures
import sys
import argparse
import shutil
import json
import os
# простите если есть говно код, тут часть кода со stackoverflow, nixos wiki и от gemini 3 pro что бы допилить;)
# select repos
REPO_MAP = {
    "23.11": "github:nixos/nixpkgs/nixos-23.11",
    "24.05": "github:nixos/nixpkgs/nixos-24.05",
    "24.11": "github:nixos/nixpkgs/nixos-24.11",
    "25.05": "github:nixos/nixpkgs/nixos-25.05",
    "25.11": "github:nixos/nixpkgs/nixos-25.11",
    "unstable": "github:nixos/nixpkgs/nixos-unstable",
    "master": "github:nixos/nixpkgs/master",
}

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def check_nix_installed():
    if not shutil.which("nix"):
        print(f"{Colors.FAIL}Ошибка: Nix не установлен или не найден в path.{Colors.ENDC}")
        sys.exit(1)

def search_in_repo(repo_name, repo_url, query):
    """
    Запуск nix search --json.
    """
    try:
        # NIXPKGS_ALLOW_UNFREE
        env = os.environ.copy()
        env["NIXPKGS_ALLOW_UNFREE"] = "1"

        #  nix search --json
        result = subprocess.run(
            ["nix", "search", "--json", repo_url, query],
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode != 0:
            # ignor err
            if not result.stdout.strip():
                return []

        # pars JSON
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            
            return []

        found_packages = []
        
        
        for key, info in data.items():
            
            pkg_name = key.split(".")[-1]
            description = info.get("description", "Нет описания")
            version = info.get("version", "unknown")
            
            found_packages.append({
                "repo": repo_name,
                "name": pkg_name,
                "version": version,
                "desc": description
            })
                
        return found_packages

    except Exception as e:
        
        return []

def main():
    check_nix_installed()

    parser = argparse.ArgumentParser(description="Multi-channel NixOS Package Searcher (JSON Mode)")
    parser.add_argument("query", nargs="?", help="Название пакета для поиска")
    parser.add_argument("-r", "--repos", nargs="+", help="Список репозиториев")
    
    args = parser.parse_args()

    query = args.query
    if not query:
        print(f"{Colors.HEADER}=== NixOS Multi-Repo Search (JSON) ==={Colors.ENDC}")
        query = input(f"{Colors.CYAN}Введите название пакета: {Colors.ENDC}").strip()
        if not query:
            sys.exit(0)

    target_repos = []
    if args.repos:
        for r in args.repos:
            if r in REPO_MAP:
                target_repos.append(r)
    else:
        print(f"\n{Colors.BLUE}Доступные репозитории:{Colors.ENDC}")
        repo_keys = list(REPO_MAP.keys())
        for i, key in enumerate(repo_keys):
            print(f"[{i+1}] {key}")
        
        choice = input(f"\n{Colors.CYAN}Выберите номера через пробел (Enter = искать везде): {Colors.ENDC}").strip()
        
        if not choice:
            target_repos = repo_keys
        else:
            try:
            
                if " " not in choice and len(choice) > 1:
                    print(f"{Colors.WARNING}Вы ввели цифры слитно. Пытаюсь разделить...{Colors.ENDC}")
                    indices = [int(digit) - 1 for digit in choice] 
                else:
                    indices = [int(x) - 1 for x in choice.split()]

                for idx in indices:
                    if 0 <= idx < len(repo_keys):
                        target_repos.append(repo_keys[idx])
            except ValueError:
                target_repos = repo_keys

    print(f"\n{Colors.BOLD}Ищем '{query}' в: {', '.join(target_repos)}...{Colors.ENDC}")
    print(f"{Colors.WARNING}(Ждем ответ от JSON API Nix...){Colors.ENDC}\n")

    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_repo = {
            executor.submit(search_in_repo, repo, REPO_MAP[repo], query): repo 
            for repo in target_repos
        }
        
        for future in concurrent.futures.as_completed(future_to_repo):
            repo = future_to_repo[future]
            try:
                data = future.result()
                results[repo] = data
            except Exception:
                results[repo] = []

    # result:
    found_something = False
    print("-" * 60)
    sorted_repos = [r for r in REPO_MAP.keys() if r in results]
    
    for repo in sorted_repos:
        pkgs = results[repo]
        if not pkgs:
            continue
            
        found_something = True
        print(f"{Colors.HEADER}>>> Репозиторий: {repo}{Colors.ENDC}")
        for pkg in pkgs:
            name = pkg['name']
            version = pkg['version']
            desc = pkg['desc']
            
            # color name
            if query.lower() in name.lower():
                name_display = f"{Colors.GREEN}{Colors.BOLD}{name}{Colors.ENDC}"
            else:
                name_display = f"{Colors.GREEN}{name}{Colors.ENDC}"
            
            print(f"  📦 {name_display} {Colors.WARNING}(v{version}){Colors.ENDC}")
            # short name
            if desc and len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"     {Colors.BLUE}{desc}{Colors.ENDC}")
        print("")

    if not found_something:
        print(f"{Colors.FAIL}Ничего не найдено.{Colors.ENDC}")
        print("Подсказка: Nix ищет только точное вхождение слов в имя или описание.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
