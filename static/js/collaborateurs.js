// ==============================
// 🟢 MODALS
// ==============================
window.openAddModal = function () {
  const m = document.getElementById("addModal"), c = document.getElementById("addModalContent");
  m.classList.remove("hidden");
  setTimeout(() => {
    c.classList.remove("scale-95", "opacity-0");
    c.classList.add("scale-100", "opacity-100");
  }, 50);
};

window.closeAddModal = function () {
  const m = document.getElementById("addModal"), c = document.getElementById("addModalContent");
  c.classList.remove("scale-100", "opacity-100");
  c.classList.add("scale-95", "opacity-0");
  setTimeout(() => m.classList.add("hidden"), 150);
};

window.openEditModal = function (matricule, nom, prenom, profil_id, affectation_id, build, run, heures_base) {
  const m = document.getElementById("editModal"), c = document.getElementById("editModalContent");

  document.getElementById("editMatricule").value = matricule;
  document.getElementById("editNom").value = nom;
  document.getElementById("editPrenom").value = prenom;
  document.getElementById("editProfil").value = profil_id;
  document.getElementById("editAffectation").value = affectation_id;
  document.getElementById("editHeuresBase").value = heures_base;
  document.getElementById("editBuild").value = build;
  document.getElementById("editRun").value = run;
  document.getElementById("editForm").action = `/collaborateurs/modifier/${matricule}`;
  loadRepartitions(matricule);

  m.classList.remove("hidden");
  setTimeout(() => {
    c.classList.remove("scale-95", "opacity-0");
    c.classList.add("scale-100", "opacity-100");
  }, 50);
};

window.closeEditModal = function () {
  const m = document.getElementById("editModal"), c = document.getElementById("editModalContent");
  c.classList.remove("scale-100", "opacity-100");
  c.classList.add("scale-95", "opacity-0");
  setTimeout(() => m.classList.add("hidden"), 150);
};

// ==============================
// 🟣 AJOUT Répartition secondaire
// ==============================
window.ajouterRepartitionTemp = function () {
  const profilSelect = document.getElementById("repProfil");
  const buildInput = document.getElementById("repBuild");
  const runInput = document.getElementById("repRun");
  const tbody = document.getElementById("repartitionTableBody");

  const profil_id = profilSelect.value;
  const profil_nom = profilSelect.options[profilSelect.selectedIndex]?.text || "";
  const build = (buildInput.value || "").trim();
  const run = (runInput.value || "").trim();

  if (!profil_id || build === "" || run === "") {
    alert("Veuillez remplir tous les champs.");
    return;
  }
  if (parseFloat(build) + parseFloat(run) > 100) {
    alert("Build + Run ne doit pas dépassé 100%.");
    return;
  }

  if (tbody.children.length === 1 && tbody.children[0].textContent.includes("Aucune")) {
    tbody.innerHTML = "";
  }

  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td class="px-3 py-2"><input type="hidden" name="rep_profil_id[]" value="${profil_id}">${profil_nom}</td>
    <td class="px-3 py-2 text-center"><input type="number" name="rep_build[]" value="${build}" class="text-center border rounded w-20 py-1 text-sm"></td>
    <td class="px-3 py-2 text-center"><input type="number" name="rep_run[]" value="${run}" class="text-center border rounded w-20 py-1 text-sm"></td>
    <td class="px-3 py-2 text-center">
      <button type="button" onclick="this.closest('tr').remove();" class="bg-red-100 text-red-600 px-2 py-1 rounded text-xs hover:bg-red-200">🗑️ Supprimer</button>
    </td>`;
  tbody.appendChild(tr);

  profilSelect.value = "";
  buildInput.value = "";
  runInput.value = "";
};

// ==============================
// 🔵 MODIF Répartition secondaire
// ==============================
window.ajouterRepartitionEdit = function () {
  const profilSelect = document.getElementById("editRepProfil");
  const buildInput = document.getElementById("editRepBuild");
  const runInput = document.getElementById("editRepRun");
  const tbody = document.getElementById("editRepartitionTableBody");

  const profil_id = profilSelect.value;
  const profil_nom = profilSelect.options[profilSelect.selectedIndex]?.text || "";
  const build = (buildInput.value || "").trim();
  const run = (runInput.value || "").trim();

  if (!profil_id || build === "" || run === "") {
    alert("Veuillez remplir tous les champs.");
    return;
  }
  if (parseFloat(build) + parseFloat(run) > 100) {
    alert("Build + Run ne doit pas dépassé 100%.");
    return;
  }

  if (tbody.children.length === 1 && tbody.children[0].textContent.includes("Aucune")) {
    tbody.innerHTML = "";
  }

  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td class="px-3 py-2"><input type="hidden" name="rep_profil_id[]" value="${profil_id}">${profil_nom}</td>
    <td class="px-3 py-2 text-center"><input type="number" name="rep_build[]" value="${build}" class="text-center border rounded w-20 py-1 text-sm"></td>
    <td class="px-3 py-2 text-center"><input type="number" name="rep_run[]" value="${run}" class="text-center border rounded w-20 py-1 text-sm"></td>
    <td class="px-3 py-2 text-center">
      <button type="button" onclick="this.closest('tr').remove();" class="bg-red-100 text-red-600 px-2 py-1 rounded text-xs hover:bg-red-200">🗑️ Supprimer</button>
    </td>`;
  tbody.appendChild(tr);

  profilSelect.value = "";
  buildInput.value = "";
  runInput.value = "";
};
// ==============================
// 🟠 CHARGER LES RÉPARTITIONS EXISTANTES (dans le modal d'édition)
// ==============================
// ==============================
// 🟠 CHARGER LES RÉPARTITIONS EXISTANTES (dans le modal d'édition)
// ==============================
async function loadRepartitions(matricule) {
  try {
    const res = await fetch(`/collaborateurs/repartition/get/${matricule}`);
    const data = await res.json();
    const tbody = document.getElementById("editRepartitionTableBody");

    tbody.innerHTML = "";

    if (!data.repartitions || data.repartitions.length === 0) {
      tbody.innerHTML = `
        <tr class="text-gray-500 text-center">
          <td colspan="4" class="py-2 italic">Aucune répartition secondaire</td>
        </tr>`;
      return;
    }

    data.repartitions.forEach(rep => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-3 py-2">
          <input type="hidden" name="rep_profil_id[]" value="${rep.profil_id}">
          ${rep.profil_nom}
        </td>
        <td class="px-3 py-2 text-center">
          <input type="number" name="rep_build[]" value="${rep.pourcentage_build}"
                 class="text-center border rounded w-20 py-1 text-sm">
        </td>
        <td class="px-3 py-2 text-center">
          <input type="number" name="rep_run[]" value="${rep.pourcentage_run}"
                 class="text-center border rounded w-20 py-1 text-sm">
        </td>
        <td class="px-3 py-2 text-center">
          <button type="button" onclick="this.closest('tr').remove();"
                  class="bg-red-100 text-red-600 px-2 py-1 rounded text-xs hover:bg-red-200">🗑️ Supprimer</button>
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("❌ Erreur lors du chargement des répartitions :", err);
  }
}

/// ==========================================================
// 🧮 CONTRÔLE CAF SECONDAIRES AVANT ENREGISTREMENT (AJOUT)
// ==========================================================
document.addEventListener("DOMContentLoaded", () => {
  const addForm = document.querySelector("#addModal form");
  if (addForm) {
    addForm.addEventListener("submit", (e) => {
      const heuresBaseInput = addForm.querySelector("input[name='heures_base']");
      const pBuildMain = parseFloat(addForm.querySelector("input[name='pourcentage_build']").value || 0);
      const pRunMain = parseFloat(addForm.querySelector("input[name='pourcentage_run']").value || 0);
      const heuresBase = parseFloat(heuresBaseInput.value || 0);

      const cafBuildDispo = (pBuildMain / 100) * heuresBase;
      const cafRunDispo = (pRunMain / 100) * heuresBase;

      let totalBuild = 0;
      let totalRun = 0;

      document.querySelectorAll("#repartitionTableBody tr").forEach((tr) => {
        const buildInput = tr.querySelector("input[name='rep_build[]']");
        const runInput = tr.querySelector("input[name='rep_run[]']");
        if (!buildInput || !runInput) return;

        const rb = parseFloat(buildInput.value || 0);
        const rr = parseFloat(runInput.value || 0);

        totalBuild += (rb / 100) * cafBuildDispo;
        totalRun += (rr / 100) * cafRunDispo;
      });

      if (totalBuild > cafBuildDispo || totalRun > cafRunDispo) {
        e.preventDefault();
        e.stopImmediatePropagation();
        alert(
          `⚠️ Erreur : la somme des CAF secondaires dépasse les CAF disponibles du collaborateur.\n\n` +
          `CAF principal : ${cafBuildDispo.toFixed(2)} (Build) / ${cafRunDispo.toFixed(2)} (Run)\n` +
          `CAF secondaires : ${totalBuild.toFixed(2)} (Build) / ${totalRun.toFixed(2)} (Run)`
        );
        document.querySelector("#repartitionTableBody").classList.add("bg-red-100");
        setTimeout(() => {
          document.querySelector("#repartitionTableBody").classList.remove("bg-red-100");
        }, 2000);
        return false;
      }
    });
  }

  // ==========================================================
  // 🧮 CONTRÔLE CAF SECONDAIRES AVANT MODIFICATION (ÉDITION)
  // ==========================================================
  const editForm = document.querySelector("#editModal form");
  if (editForm) {
    editForm.addEventListener("submit", (e) => {
      const heuresBaseInput = document.getElementById("editHeuresBase");
      const pBuildMain = parseFloat(document.getElementById("editBuild").value || 0);
      const pRunMain = parseFloat(document.getElementById("editRun").value || 0);
      const heuresBase = parseFloat(heuresBaseInput.value || 0);

      const cafBuildDispo = (pBuildMain / 100) * heuresBase;
      const cafRunDispo = (pRunMain / 100) * heuresBase;

      let totalBuild = 0;
      let totalRun = 0;

      document.querySelectorAll("#editRepartitionTableBody tr").forEach((tr) => {
        const buildInput = tr.querySelector("input[name='rep_build[]']");
        const runInput = tr.querySelector("input[name='rep_run[]']");
        if (!buildInput || !runInput) return;

        const rb = parseFloat(buildInput.value || 0);
        const rr = parseFloat(runInput.value || 0);

        totalBuild += (rb / 100) * cafBuildDispo;
        totalRun += (rr / 100) * cafRunDispo;
      });

      if (totalBuild > cafBuildDispo || totalRun > cafRunDispo) {
        e.preventDefault();
        e.stopImmediatePropagation();
        alert(
          `⚠️ Erreur : la somme des CAF secondaires dépasse les CAF disponibles du collaborateur.\n\n` +
          `CAF principal : ${cafBuildDispo.toFixed(2)} (Build) / ${cafRunDispo.toFixed(2)} (Run)\n` +
          `CAF secondaires : ${totalBuild.toFixed(2)} (Build) / ${totalRun.toFixed(2)} (Run)`
        );
        document.querySelector("#editRepartitionTableBody").classList.add("bg-red-100");
        setTimeout(() => {
          document.querySelector("#editRepartitionTableBody").classList.remove("bg-red-100");
        }, 2000);
        return false;
      }
    });
  }
});
