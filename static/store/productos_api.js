const apiProducts = document.getElementById("api-products");
const apiStatus = document.getElementById("api-status");

async function loadApiProducts() {
  const url = new URL(apiProducts.dataset.apiUrl, window.location.origin);
  url.searchParams.set("query", "{ products { name price stock category { name } } }");

  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (result.errors || !Array.isArray(result.data?.products)) {
      throw new Error("Respuesta inválida de GraphQL");
    }

    const products = result.data.products;
    if (!products.length) {
      apiStatus.textContent = "No hay productos publicados.";
      return;
    }

    for (const product of products) {
      const card = document.createElement("article");
      card.className = "catalog-card catalog-body";
      const category = document.createElement("span");
      category.className = "catalog-category";
      category.textContent = product.category.name;
      const name = document.createElement("h3");
      name.textContent = product.name;
      const price = document.createElement("strong");
      price.textContent = `$${product.price}`;
      const stock = document.createElement("p");
      stock.textContent = product.stock > 0 ? `${product.stock} disponibles` : "Sin stock";
      card.append(category, name, price, stock);
      apiProducts.append(card);
    }
    apiStatus.textContent = `${products.length} producto${products.length === 1 ? "" : "s"} obtenido${products.length === 1 ? "" : "s"} desde la API.`;
  } catch (error) {
    console.error("No se pudieron cargar los productos de la API:", error);
    apiStatus.textContent = "No pudimos consultar los productos. Intentá nuevamente más tarde.";
  }
}

loadApiProducts();
