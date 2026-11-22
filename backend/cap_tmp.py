import asyncio
from playwright.async_api import async_playwright
SAIDA = "/home/pedro/Área de trabalho/raspberryPi5/prints"
FRASE = "consumidor pagou a fatura do cartao antes do vencimento e mesmo assim o banco inscreveu o nome dele no cadastro de inadimplentes"

async def entrar(pag):
    await pag.goto("http://127.0.0.1:5174/", wait_until="networkidle")
    await pag.fill('input[type="email"]', "captura@exemplo.com.br")
    await pag.fill('input[type="password"]', "Captura123#")
    await pag.click('button:has-text("Entrar na plataforma")')
    await pag.wait_for_selector("#legal-search-input", timeout=30000)

async def buscar(pag, termo, rotulo):
    await pag.click(f'label:has-text("{rotulo}")')
    await pag.fill("#legal-search-input", termo)
    await pag.click('button:has-text("Pesquisar")')
    await pag.wait_for_selector(".decision-result-card", timeout=120000)
    await pag.wait_for_timeout(6000)

async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        pag = await nav.new_page(viewport={"width": 1680, "height": 1150})
        await entrar(pag)
        await pag.screenshot(path=f"{SAIDA}/1-campo-de-busca.png")
        print("1 placeholder:", await pag.get_attribute("#legal-search-input", "placeholder"))

        await buscar(pag, FRASE, "Palavras e assuntos parecidos")
        await pag.screenshot(path=f"{SAIDA}/2-ampliada-ordenada-por-sentido.png")
        print("2 ampliada: selos", await pag.locator(".decision-result-card__subject-tag").count(),
              "| faixas", set(await pag.locator(".decision-result-card__proximity").all_text_contents()))

        await buscar(pag, FRASE, "Só as minhas palavras")
        await pag.screenshot(path=f"{SAIDA}/3-so-as-minhas-palavras.png")
        print("3 exatas: selos", await pag.locator(".decision-result-card__subject-tag").count(),
              "| rotulos", await pag.locator(".decision-result-card__proximity").count())

        await buscar(pag, "dano moral", "Palavras e assuntos parecidos")
        await pag.screenshot(path=f"{SAIDA}/4-duas-palavras-nao-bastam.png")
        print("4 duas palavras: selos", await pag.locator(".decision-result-card__subject-tag").count())

        await pag.click("text=Panorama")
        await pag.wait_for_timeout(4000)
        await pag.screenshot(path=f"{SAIDA}/5-panorama.png")
        await nav.close()

asyncio.run(main())
