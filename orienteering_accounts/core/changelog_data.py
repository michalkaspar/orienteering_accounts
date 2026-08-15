from datetime import date

CHANGELOG_ENTRIES = [
    {
        'version': 'v0.1.0',
        'date': date(2021, 1, 15),
        'items': [
            'Spuštění aplikace pro správu účtů oddílu.',
            'Přidán filtr účtů a možnost zadávat transakce.',
            'Automatická správa přístupových práv v systému ORIS podle stavu účtu.',
        ],
    },
    {
        'version': 'v0.2.0',
        'date': date(2021, 3, 16),
        'items': [
            'Zaveden systém rolí a oprávnění pro přístup do aplikace.',
            'Přidána platební období a navigace podle nich.',
            'Umožněno vkládat stránky aplikace do iframe (např. na web oddílu).',
            'Přidán přehled a detail závodů včetně přiřazení vedoucího výpravy.',
        ],
    },
    {
        'version': 'v0.3.0',
        'date': date(2021, 4, 26),
        'items': [
            'Přidán filtr na zaplacené členské příspěvky a dluhy.',
            'Umožněna úprava zadaných transakcí.',
            'Přidán export účtů včetně registračního čísla.',
            'Zavedeno automatické zasílání platebních údajů e-mailem před závodem.',
        ],
    },
    {
        'version': 'v0.4.0',
        'date': date(2021, 6, 22),
        'items': [
            'Přepracován výpočet zůstatku účtu, včetně zohlednění zůstatku z předchozích let.',
            'Přidány dluhy za závody a jejich automatické zasílání e-mailem.',
            'Zavedeny poplatky za pozdní přihlášku na závod.',
            'Vylepšeny a personalizovány platební e-maily.',
        ],
    },
    {
        'version': 'v0.5.0',
        'date': date(2021, 9, 28),
        'items': [
            'Přidán odkaz na vyúčtování závodu a přepočet dluhů pro etapové závody.',
            'Přidány přihlášky na závody (entries) a jejich e-mailové oznámení.',
            'Import ze systému ORIS nyní aktualizuje pouze nové položky.',
            'Umožněna oprava vyúčtování.',
        ],
    },
    {
        'version': 'v0.6.0',
        'date': date(2021, 11, 14),
        'items': [
            'Přidány ostatní dluhy (mimo závody) a jejich propojení s účtem.',
            'Přidán náhled přihlášek a transakcí před odesláním.',
        ],
    },
    {
        'version': 'v0.7.0',
        'date': date(2021, 12, 20),
        'items': [
            'Zavedeno automatické zasílání informací o dluzích e-mailem.',
            'Rozšířen obsah e-mailu s dluhy a upraveno zaokrouhlování částek.',
            'Nastavena nová splatnost dluhů.',
        ],
    },
    {
        'version': 'v0.8.0',
        'date': date(2022, 2, 20),
        'items': [
            'Do importu ze závodů zahrnuty i neoficiální závody.',
            'Nová verze platebních e-mailů pro účty.',
            'V editaci účtu přidána možnost změny hesla a e-mailu.',
            'Přidán filtr vyřešených vyúčtování a jmenný filtr účtů.',
        ],
    },
    {
        'version': 'v0.9.0',
        'date': date(2022, 4, 27),
        'items': [
            'Přidáno pole "členství zaplaceno do" a filtr neaktivních účtů.',
            'Do výpočtu dluhů nově vstupují i výsledky ze závodů.',
        ],
    },
    {
        'version': 'v0.10.0',
        'date': date(2022, 10, 23),
        'items': [
            'Přidán termín splatnosti dluhů.',
            'Nová šablona platebních údajů s QR kódem pro platbu.',
            'Přidány přihlášky na štafetové závody.',
        ],
    },
    {
        'version': 'v0.11.0',
        'date': date(2023, 4, 27),
        'items': [
            'Aplikace přeložena a sjednocen vzhled (Bootstrap).',
            'Přidáno řazení sloupců v tabulkách.',
            'Doladěny platební a dluhové e-maily.',
        ],
    },
    {
        'version': 'v0.12.0',
        'date': date(2024, 2, 29),
        'items': [
            'Nastavena nová splatnost dluhů.',
            'Napojení na Google Workspace – správa uživatelů a skupin.',
            'Přidán přehled a export čísel čipů klubovny.',
            'Přidán seznam členů oddílu.',
        ],
    },
    {
        'version': 'v0.13.0',
        'date': date(2024, 4, 16),
        'items': [
            'Přidán sport lesní běh (LOB) mezi podporované sporty.',
            'Přidán druhý e-mail účtu a možnost evidovat transakce s nulovou hodnotou.',
            'V platebních e-mailech a vyúčtování nově zobrazena měna.',
        ],
    },
    {
        'version': 'v0.14.0',
        'date': date(2024, 7, 30),
        'items': [
            'Přidáno automatické zpracování a párování bankovních transakcí, včetně automatického strhávání plateb.',
            'Do dluhových e-mailů přidán variabilní symbol a QR kód pro platbu.',
            'Nová verze e-mailu s dluhy.',
        ],
    },
    {
        'version': 'v0.15.0',
        'date': date(2024, 11, 13),
        'items': [
            'Přidáno ORIS ID do platebních e-mailů.',
            'Umožněna změna hesla uživatele.',
            'Přidán přehled členů klubu.',
        ],
    },
    {
        'version': 'v0.16.0',
        'date': date(2025, 1, 21),
        'items': [
            'Nová šablona e-mailu pro platbu členského příspěvku.',
            'U bankovních transakcí nyní evidován účel platby.',
            'Přidány doplňkové služby pro štafetové závody.',
        ],
    },
    {
        'version': 'v0.17.0',
        'date': date(2025, 3, 26),
        'items': [
            'Zaplacením členského příspěvku se neaktivní člen automaticky opět aktivuje.',
            'Přidán modul sprintových štafet včetně exportu.',
            'Přidán import pořádaných závodů ze systému ORIS.',
        ],
    },
    {
        'version': 'v0.18.0',
        'date': date(2025, 4, 16),
        'items': [
            'Automatizováno odebírání přístupů z Google Workspace pro neaktivní členy.',
            'Přidána úvodní zpráva o dluhu pro účastníky, kteří na závodě nestartovali.',
        ],
    },
    {
        'version': 'v0.19.0',
        'date': date(2025, 10, 17),
        'items': [
            'U transakcí nyní evidován jejich autor.',
            'Upraveny texty a formuláře dluhových e-mailů.',
        ],
    },
    {
        'version': 'v0.20.0',
        'date': date(2025, 11, 29),
        'items': [
            'Zlepšena responzivita aplikace pro mobilní zařízení.',
            'Přidáno automatické připomenutí nezaplacených dluhů.',
            'Přechod na odesílání e-mailů přes Google SMTP.',
        ],
    },
    {
        'version': 'v0.21.0',
        'date': date(2026, 1, 4),
        'items': [
            'V přehledu transakcí odděleny transakce z aktuálního roku od starších.',
            'Přidána možnost evidovat budoucí (plánované) transakce.',
            'Nové verze informačních e-mailů.',
        ],
    },
    {
        'version': 'v0.22.0',
        'date': date(2026, 1, 30),
        'items': [
            'Vylepšen vzhled a přehlednost tabulky transakcí a vyúčtování závodů, včetně řazení sloupců a souhrnného řádku za předchozí roky.',
            'U bankovních transakcí nyní zobrazeno jméno odesílatele a poznámka příjemce.',
            'Zavedeno automatické odesílání e-mailu při přijetí transakce na účet.',
            'QR kód pro platbu dluhu nově negeneruje částku, aby šel použít opakovaně a platby se párovaly podle variabilního symbolu.',
            'Opraveno zpracování etapových závodů, aby se nezpracovávaly jako samostatné závody.',
            'Aktualizovány platební údaje pro sezónu 2026.',
        ],
    },
    {
        'version': 'v0.23.0',
        'date': date(2026, 2, 12),
        'items': [
            'Transakce nyní zpracovávány atomicky pro vyšší spolehlivost.',
            'Přidána přihlašovací stránka.',
            'Dokončen kompletní tok zpracování a ověřování bankovních transakcí.',
            'Přidáno zaslání e-mailu při obnovení přístupových práv k přihlašování.',
        ],
    },
    {
        'version': 'v0.24.0',
        'date': date(2026, 3, 31),
        'items': [
            'Export sprintových štafet nyní ve formátu XLSX místo CSV.',
            'V přehledu transakcí zobrazen štítek platby členského příspěvku.',
            'Přidána měna závodu.',
        ],
    },
    {
        'version': 'v0.25.0',
        'date': date(2026, 4, 28),
        'items': [
            'Opraven QR kód pro přeplatky (kladný zůstatek účtu).',
            'Při zrušení přihlášky se nyní mažou i budoucí naplánované transakce.',
        ],
    },
    {
        'version': 'v0.26.0',
        'date': date(2026, 7, 30),
        'items': [
            'Vedoucí výpravy je upozorněn, pokud součet dluhů v přihlášce neodpovídá vyúčtování závodu v ORIS.',
            'Opraveno sčítání duplicitních položek doplňkových služeb z ORIS.',
            'Podporováno zpracování objednávek pouze s doplňkovou službou bez přihlášky na závod.',
        ],
    },
    {
        'version': 'v0.27.0',
        'date': date(2026, 8, 2),
        'items': [
            'Aktualizovány platební údaje v e-mailu se zbývající platbou.',
        ],
    },
    {
        'version': 'v0.28.0',
        'date': date(2026, 8, 15),
        'items': [
            'Přidána veřejná stránka Novinky se seznamem změn v aplikaci.',
        ],
    },
    {
        'version': 'v0.29.0',
        'date': date.today(),
        'items': [
            'Ve patičce stránky se nyní zobrazuje aktuální verze aplikace s odkazem na Novinky.',
        ],
    },
]
