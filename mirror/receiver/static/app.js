(() => {
  const $ = id => document.getElementById(id);
  let ready = false, config, sources = [], polling = false;
  const controls = ["save", "import", "identity", "copy", "disks"];
  function lock() { ready = false; controls.forEach(id => $(id).disabled = true); }
  async function api(path, method="GET", body) {
    const response = await fetch(`v1/${path}`, {method, signal:AbortSignal.timeout(15000), headers:{"Content-Type":"application/json", "X-Steward-UI":"1"}, body:body === undefined ? undefined : JSON.stringify(body)});
    const result = await response.json(); if (!response.ok) throw Error(result.error || "Não foi possível concluir o pedido."); return result;
  }
  function showSources() {
    $("sources").replaceChildren();
    for (const source of sources) {
      const card = document.createElement("div"); card.className = "mirror-source";
      const title = document.createElement("strong"); title.textContent = source.name;
      const note = document.createElement("small"); note.textContent = `Conta mirror_${source.name} · ${config.mount}/${source.name}`;
      const remove = document.createElement("button"); remove.type="button"; remove.className="secondary"; remove.textContent="Remover autorização";
      remove.onclick=()=>{sources=sources.filter(s=>s!==source);showSources();};
      card.append(title,note,remove); $("sources").append(card);
    }
  }
  async function refresh(initial=false) {
    if (polling) return; polling=true; lock();
    try {
      const status = await api("status");
      if (typeof status.listening !== "boolean" || typeof status.restart_required !== "boolean" || !Array.isArray(status.config?.sources)) throw Error("Estado incompleto");
      if (!config || initial) {
        config=status.config; sources=structuredClone(config.sources);
        for(const [key,value] of Object.entries(config)){const input=$("settings").elements.namedItem(key);if(input){if(input.type==="checkbox")input.checked=value;else input.value=value;}}
        showSources();
      }
      ready=true; controls.forEach(id=>$(id).disabled=false); $("copy").disabled=!$("identity-value").value;
      $("version").textContent=`v${status.version}`;
      $("mode").textContent=status.listening?"Receção ativa":"Receção desativada";
      $("status-label").textContent=status.listening?"Pronto para receber":"Sem ligações de dados";
      $("title").textContent=status.listening?"O teu espelho tem casa aqui.":"Prepara o destino ao teu ritmo.";
      $("description").textContent=status.listening?"Alicante pode enviar as origens autorizadas, diretamente por SSH.":"Confirma o disco, importa as chaves e ativa a receção quando estiveres pronto.";
      $("notice").hidden=!status.restart_required&&!status.error;
      $("notice").textContent=status.restart_required?"Configuração guardada. Reinicia manualmente esta app para aplicar as alterações. O recetor continua com a configuração do último arranque.":status.error||"";
      $("activity").replaceChildren();
      const names={waiting:"A aguardar",receiving:"A receber ou comparar",success:"Última operação concluída",failed:"Última operação falhou"};
      for(const item of status.sources){const p=document.createElement("p");p.textContent=`${item.name} · ${names[item.status]||"A aguardar"}${item.time?" · "+new Date(item.time).toLocaleString("pt-PT"):""}`;$("activity").append(p);}
    } catch { lock();$("status-label").textContent="Ligação indisponível";$("description").textContent="Aguarda a confirmação do estado antes de alterar a configuração."; }
    finally {polling=false;}
  }
  $("settings").onsubmit=async event=>{
    event.preventDefault();if(!ready)return;
    const next={...config,sources};
    for(const input of event.target.elements)if(input.name)next[input.name]=input.type==="checkbox"?input.checked:input.type==="number"?Number(input.value):input.value.trim();
    try{config=await api("config","PUT",next);$("error").textContent="Configuração guardada. Reinicia esta app para aplicar.";await refresh();}catch(e){$("error").textContent=e.message;}
  };
  $("import").onclick=()=>{
    if(!ready)return;
    try{const data=JSON.parse($("pairing").value);if(data.protocol!=="steward-mirror-v1"||!Array.isArray(data.sources)||!data.sources.length||data.sources.length>20||data.sources.some(s=>typeof s.name!=="string"||typeof s.public_key!=="string"))throw Error();sources=data.sources.map(s=>({name:s.name,public_key:s.public_key}));showSources();$("error").textContent="Chaves importadas. Guarda para autorizar estas origens.";}catch{$("error").textContent="Cola o emparelhamento público exportado pelo Data Steward.";}
  };
  $("identity").onclick=async()=>{if(!ready)return;try{$("identity-value").value=JSON.stringify(await api("identity","POST",{}),null,2);$("identity-value").hidden=$("copy").hidden=false;$("copy").disabled=false;}catch(e){$("error").textContent=e.message;}};
  $("copy").onclick=async()=>{if(!ready)return;try{await navigator.clipboard.writeText($("identity-value").value);}catch{$("identity-value").select();}};
  $("disks").onchange=()=>{if(!ready)return;try{const disk=JSON.parse($("disks").value);$("settings").elements.mount.value=disk.mount;$("settings").elements.uuid.value=disk.uuid;}catch{/* Manual entry remains available. */}};
  async function load(){await refresh(true);if(ready)try{const data=await api("disks");for(const disk of data.disks){const option=document.createElement("option");option.value=JSON.stringify(disk);option.textContent=`${disk.mount} · ext4`;$("disks").append(option);}}catch{/* Optional discovery cannot block manual setup. */}}
  load();setInterval(refresh,5000);
})();
