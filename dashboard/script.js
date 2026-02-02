fetch("https://api.mittnamn.workers.dev")
.then(r=>r.json())
.then(d=>{
  document.getElementById("cards").innerText = `Total plays: ${d.total_plays}`;
  d.top_users.forEach(u=>{
    const li=document.createElement("li");
    li.textContent=`${u.name} — ${u.plays}`;
    board.appendChild(li);
  });
  invite.href=d.invite_url;
});
