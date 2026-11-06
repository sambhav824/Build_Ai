/**
 * BuildSmart 3D Studio - Viewport Engine & BIM Controller
 * Three.js 360° Interactive Architectural Visualization
 */

// Application Global State
const StudioState = {
  currentProjectId: 'STU-SAMPLE-2BHK',
  sceneData: null,
  bimTreeData: null,
  materialsMap: {},
  selectedMesh: null,
  highlightedMesh: null,
  visualStyle: 'realistic', // 'realistic', 'wireframe', 'transparent'
  explodedFactor: 0.0,
  currentFloorFilter: 'ALL',
  showGrid: true,
};

// Three.js Core Objects
let scene, camera, renderer, controls;
let gridHelper, raycaster, mouse;
let buildingGroup; // Root Three.js Group holding all building meshes
const meshMap = new Map(); // mesh_id -> THREE.Mesh

/**
 * Initialize 3D Viewport on DOM Load
 */
window.addEventListener('DOMContentLoaded', async () => {
  initThreeViewport();
  await loadAvailableMaterials();
  await loadProject(StudioState.currentProjectId);
  setupViewportEvents();
});

/**
 * Initialize WebGL Canvas, Scene, PerspectiveCamera, OrbitControls, and Lighting
 */
function initThreeViewport() {
  const container = document.getElementById('viewportContainer');
  const canvas = document.getElementById('studioCanvas');

  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f1318);
  scene.fog = new THREE.FogExp2(0x0f1318, 0.008);

  // Camera
  const aspect = container.clientWidth / container.clientHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
  camera.position.set(18, 14, 18);

  // Renderer
  renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // OrbitControls
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = true;
  controls.maxPolarAngle = Math.PI / 2 - 0.02; // Keep camera above ground
  controls.minDistance = 2.0;
  controls.maxDistance = 200.0;
  controls.target.set(6, 3, -4.5);

  // Lighting Setup
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
  scene.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xfffaf0, 0.95);
  sunLight.position.set(25, 40, 25);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 0.5;
  sunLight.shadow.camera.far = 150;
  const d = 25;
  sunLight.shadow.camera.left = -d;
  sunLight.shadow.camera.right = d;
  sunLight.shadow.camera.top = d;
  sunLight.shadow.camera.bottom = -d;
  sunLight.shadow.bias = -0.0005;
  scene.add(sunLight);

  const fillLight = new THREE.DirectionalLight(0xdbeafe, 0.35);
  fillLight.position.set(-20, 25, -20);
  scene.add(fillLight);

  // Ground Grid
  gridHelper = new THREE.GridHelper(60, 60, 0xd4a853, 0x2c3542);
  gridHelper.position.y = -0.01;
  scene.add(gridHelper);

  // Building root group
  buildingGroup = new THREE.Group();
  scene.add(buildingGroup);

  // Interaction Raycaster
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  // Animation Loop
  animate();

  // Resize Listener
  window.addEventListener('resize', onWindowResize);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

function onWindowResize() {
  const container = document.getElementById('viewportContainer');
  if (!container || !renderer || !camera) return;
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

/**
 * Load Materials from Backend API
 */
async function loadAvailableMaterials() {
  try {
    const res = await fetch('/api/studio/materials');
    if (res.ok) {
      StudioState.materialsMap = await res.json();
      populateMaterialDropdown(StudioState.materialsMap);
    }
  } catch (err) {
    console.warn('Could not fetch materials API:', err);
  }
}

function populateMaterialDropdown(materials) {
  const select = document.getElementById('inspMaterialSelect');
  if (!select) return;
  select.innerHTML = '';
  for (const [id, m] of Object.entries(materials)) {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = `${m.name} (${m.category})`;
    select.appendChild(opt);
  }
}

/**
 * Load Architectural Project (Scene Graph + BIM Tree)
 */
async function loadProject(projectId) {
  try {
    // 1. Fetch Scene Graph
    const sceneRes = await fetch(`/api/studio/projects/${projectId}/scene`);
    if (!sceneRes.ok) {
      console.warn(`Project ${projectId} not found. Seeding sample...`);
      await fetch('/api/studio/seed-sample', { method: 'POST' });
      return loadProject('STU-SAMPLE-2BHK');
    }
    StudioState.sceneData = await sceneRes.json();
    StudioState.currentProjectId = projectId;

    // 2. Fetch BIM Tree
    const bimRes = await fetch(`/api/studio/projects/${projectId}/bim-tree`);
    if (bimRes.ok) {
      StudioState.bimTreeData = await bimRes.json();
      renderBIMTree(StudioState.bimTreeData);
    }

    // 3. Populate Header info
    document.getElementById('headerProjectName').textContent = StudioState.sceneData.project_name || 'Architectural Model';

    // 4. Build 3D Meshes in Viewport
    build3DScene(StudioState.sceneData);

    // 5. Update Floor Filter Dropdown
    updateFloorFilterOptions(StudioState.sceneData.levels);

  } catch (err) {
    console.error('Failed to load project:', err);
  }
}

/**
 * Build Three.js Meshes from Scene Graph JSON
 */
function build3DScene(sceneData) {
  // Clear previous meshes
  while (buildingGroup.children.length > 0) {
    const obj = buildingGroup.children[0];
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
      else obj.material.dispose();
    }
    buildingGroup.remove(obj);
  }
  meshMap.clear();

  // Create PBR materials
  const materialInstances = {};
  for (const [id, m] of Object.entries(sceneData.materials)) {
    materialInstances[id] = new THREE.MeshStandardMaterial({
      color: new THREE.Color(m.color),
      roughness: m.roughness !== undefined ? m.roughness : 0.65,
      metalness: m.metalness !== undefined ? m.metalness : 0.1,
      transparent: !!m.transparent,
      opacity: m.opacity !== undefined ? m.opacity : 1.0,
      side: THREE.DoubleSide,
    });
  }

  // Build each element mesh
  for (const m of sceneData.meshes) {
    const [dx, dy, dz] = m.dimensions;
    const geometry = new THREE.BoxGeometry(dx, dy, dz);

    const baseMat = materialInstances[m.material_id] || new THREE.MeshStandardMaterial({ color: 0xd3d3d3, roughness: 0.7 });
    const material = baseMat.clone(); // Clone so individual element edits don't overwrite entire category

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(m.position[0], m.position[1], m.position[2]);
    if (m.rotation) {
      mesh.rotation.set(m.rotation[0], m.rotation[1], m.rotation[2]);
    }

    mesh.castShadow = true;
    mesh.receiveShadow = true;

    // Attach metadata for raycasting & inspector
    mesh.userData = {
      mesh_id: m.mesh_id,
      element_id: m.element_id,
      category: m.category,
      name: m.name,
      wall_type: m.wall_type,
      floor_index: m.floor_index,
      floor_name: m.floor_name,
      dimensions: m.dimensions,
      material_id: m.material_id,
      baseElevationY: m.position[1], // for exploded view
      originalColor: material.color.getHex(),
    };

    buildingGroup.add(mesh);
    meshMap.set(m.mesh_id, mesh);
  }

  // Adjust Camera target and position based on scene bounding box
  if (sceneData.camera) {
    const t = sceneData.camera.target;
    const p = sceneData.camera.initial_position;
    controls.target.set(t[0], t[1], t[2]);
    camera.position.set(p[0], p[1], p[2]);
    controls.update();
  }
}

/**
 * Render Left Panel BIM Tree Hierarchy
 */
function renderBIMTree(tree) {
  if (!tree) return;

  // Stats
  document.getElementById('bimTotalBuiltup').textContent = `${tree.total_builtup_sqm || 0} m²`;
  document.getElementById('statHeight').textContent = `${tree.total_height_m || 0} m`;
  document.getElementById('statFootprint').textContent = `${tree.levels?.[0]?.builtup_sqm || 0} m²`;

  // Stories List
  const levelsList = document.getElementById('bimLevelsList');
  levelsList.innerHTML = '';
  document.getElementById('bimLevelCount').textContent = tree.levels?.length || 0;

  tree.levels.forEach((lvl, idx) => {
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between px-2 py-1.5 rounded bg-cad-bg hover:bg-cad-hover text-cad-text transition cursor-pointer';
    div.innerHTML = `
      <div class="flex items-center space-x-2">
        <i class="fa-solid fa-layer-group text-desert text-xs"></i>
        <span class="font-medium">${lvl.name}</span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-[10px] font-mono text-cad-muted">${lvl.builtup_sqm} m²</span>
        <button onclick="toggleFloorVisibility(${idx}, event)" class="text-cad-muted hover:text-white" title="Toggle Visibility">
          <i class="fa-solid fa-eye text-xs"></i>
        </button>
      </div>
    `;
    div.onclick = () => filterFloor(idx.toString());
    levelsList.appendChild(div);
  });

  // Building Elements List
  const elemList = document.getElementById('bimElementsList');
  elemList.innerHTML = '';
  let totalElems = 0;

  tree.building_elements?.forEach(elem => {
    totalElems += elem.count;
    const div = document.createElement('div');
    div.className = 'flex items-center justify-between px-2 py-1.5 rounded hover:bg-cad-hover text-cad-text transition cursor-pointer';
    div.innerHTML = `
      <div class="flex items-center space-x-2">
        <i class="fa-solid ${elem.icon || 'fa-cube'} text-desert text-xs w-4"></i>
        <span>${elem.category}</span>
      </div>
      <span class="font-mono text-[11px] bg-cad-bg px-1.5 py-0.5 rounded text-cad-muted">${elem.count}</span>
    `;
    div.onclick = () => filterByCategory(elem.category);
    elemList.appendChild(div);
  });

  document.getElementById('bimTotalElements').textContent = totalElems;
}

function updateFloorFilterOptions(levels) {
  const select = document.getElementById('floorSelect');
  if (!select || !levels) return;
  select.innerHTML = '<option value="ALL">All Floors (Full Building)</option>';
  levels.forEach((lvl, idx) => {
    const opt = document.createElement('option');
    opt.value = idx.toString();
    opt.textContent = `${lvl.name} (Elev: +${lvl.elevation_m}m)`;
    select.appendChild(opt);
  });
}

/**
 * Viewport Interaction Events (Hover, Click Selection, Gizmo)
 */
function setupViewportEvents() {
  const container = document.getElementById('viewportContainer');
  const tooltip = document.getElementById('hoverTooltip');
  const tooltipName = document.getElementById('hoverElementName');
  const tooltipDetails = document.getElementById('hoverElementDetails');

  container.addEventListener('mousemove', (event) => {
    const rect = container.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / container.clientWidth) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / container.clientHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const visibleMeshes = buildingGroup.children.filter(m => m.visible);
    const intersects = raycaster.intersectObjects(visibleMeshes, false);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      if (StudioState.highlightedMesh !== hit && hit !== StudioState.selectedMesh) {
        resetHighlight();
        StudioState.highlightedMesh = hit;
        hit.material.emissive = new THREE.Color(0xd4a853);
        hit.material.emissiveIntensity = 0.35;
      }
      // Show tooltip
      tooltip.style.left = `${event.clientX - rect.left + 15}px`;
      tooltip.style.top = `${event.clientY - rect.top + 15}px`;
      tooltip.classList.remove('hidden');
      tooltipName.textContent = `${hit.userData.category}: ${hit.userData.name}`;
      const d = hit.userData.dimensions;
      tooltipDetails.textContent = `${d[0]}m (L) x ${d[1]}m (H) x ${d[2]}m (T)`;
    } else {
      resetHighlight();
      tooltip.classList.add('hidden');
    }
  });

  container.addEventListener('click', (event) => {
    raycaster.setFromCamera(mouse, camera);
    const visibleMeshes = buildingGroup.children.filter(m => m.visible);
    const intersects = raycaster.intersectObjects(visibleMeshes, false);

    if (intersects.length > 0) {
      selectMesh(intersects[0].object);
    } else {
      clearSelection();
    }
  });
}

function resetHighlight() {
  if (StudioState.highlightedMesh && StudioState.highlightedMesh !== StudioState.selectedMesh) {
    StudioState.highlightedMesh.material.emissive = new THREE.Color(0x000000);
    StudioState.highlightedMesh.material.emissiveIntensity = 0.0;
    StudioState.highlightedMesh = null;
  }
}

/**
 * Element Selection & Right Property Inspector Population
 */
function selectMesh(mesh) {
  clearSelection();
  StudioState.selectedMesh = mesh;

  // Golden highlight
  mesh.material.emissive = new THREE.Color(0xd4a853);
  mesh.material.emissiveIntensity = 0.65;

  const u = mesh.userData;
  const d = u.dimensions;

  // Update Right Panel UI
  document.getElementById('selectedCategoryBadge').textContent = u.category.toUpperCase();
  document.getElementById('inspElementId').textContent = u.element_id || u.mesh_id;
  document.getElementById('inspElementName').textContent = u.name;
  document.getElementById('inspElementStory').textContent = u.floor_name || `Level ${u.floor_index + 1}`;
  document.getElementById('inspElementType').textContent = u.wall_type || u.category;

  document.getElementById('inspDimLength').textContent = `${d[0]} m`;
  document.getElementById('inspDimHeight').textContent = `${d[1]} m`;
  document.getElementById('inspDimThickness').textContent = `${d[2]} m`;
  const area = roundTo(d[0] * d[1], 2);
  document.getElementById('inspDimArea').textContent = `${area} m²`;

  // Material Info
  const matId = u.material_id || 'MAT-PLAS-01';
  const matInfo = StudioState.materialsMap[matId] || { name: 'Standard Plaster', color_hex: '#E2E8F0', category: 'WALL_FINISH' };
  document.getElementById('inspCurrentMaterialName').textContent = matInfo.name;
  document.getElementById('inspMaterialSelect').value = matId;
  document.getElementById('inspMaterialColorSwatch').style.backgroundColor = matInfo.color_hex;
  document.getElementById('inspMaterialHex').textContent = matInfo.color_hex;
  document.getElementById('inspMaterialCategory').textContent = matInfo.category;

  document.getElementById('viewportPrompt').innerHTML = `Selected: <strong class="text-desert">${u.name}</strong>`;
}

function clearSelection() {
  if (StudioState.selectedMesh) {
    StudioState.selectedMesh.material.emissive = new THREE.Color(0x000000);
    StudioState.selectedMesh.material.emissiveIntensity = 0.0;
    StudioState.selectedMesh = null;
  }
  document.getElementById('selectedCategoryBadge').textContent = 'No Selection';
  document.getElementById('inspElementId').textContent = '-';
  document.getElementById('inspElementName').textContent = '-';
  document.getElementById('inspElementStory').textContent = '-';
  document.getElementById('inspElementType').textContent = '-';
  document.getElementById('inspDimLength').textContent = '-';
  document.getElementById('inspDimHeight').textContent = '-';
  document.getElementById('inspDimThickness').textContent = '-';
  document.getElementById('inspDimArea').textContent = '-';
  document.getElementById('viewportPrompt').textContent = 'Click any element to inspect & edit';
}

/**
 * Apply Material Live from Inspector Dropdown
 */
async function applySelectedMaterial(materialId) {
  if (!StudioState.selectedMesh) return;
  const matInfo = StudioState.materialsMap[materialId];
  if (!matInfo) return;

  // Update Three.js mesh material live
  const newColor = new THREE.Color(matInfo.color_hex);
  StudioState.selectedMesh.material.color = newColor;
  StudioState.selectedMesh.material.roughness = matInfo.roughness !== undefined ? matInfo.roughness : 0.65;
  StudioState.selectedMesh.material.metalness = matInfo.metalness !== undefined ? matInfo.metalness : 0.1;
  StudioState.selectedMesh.userData.material_id = materialId;

  // Update Inspector visuals
  document.getElementById('inspCurrentMaterialName').textContent = matInfo.name;
  document.getElementById('inspMaterialColorSwatch').style.backgroundColor = matInfo.color_hex;
  document.getElementById('inspMaterialHex').textContent = matInfo.color_hex;
  document.getElementById('inspMaterialCategory').textContent = matInfo.category;

  // Persist to backend
  try {
    const elemId = StudioState.selectedMesh.userData.element_id;
    await fetch(`/api/studio/projects/${StudioState.currentProjectId}/elements/${elemId}/material`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ material_id: materialId }),
    });
  } catch (err) {
    console.warn('Failed to save material change:', err);
  }
}

/**
 * Exploded View Slider
 */
function setExplodedHeight(val) {
  const percent = parseFloat(val);
  StudioState.explodedFactor = percent / 100.0;
  document.getElementById('explodeValue').textContent = `${percent}%`;

  buildingGroup.children.forEach(mesh => {
    const floorIdx = mesh.userData.floor_index || 0;
    const baseElev = mesh.userData.baseElevationY || 0;
    // Displace higher floors vertically
    mesh.position.y = baseElev + floorIdx * StudioState.explodedFactor * 4.0;
  });
}

/**
 * Floor Level Filtering
 */
function filterFloor(val) {
  StudioState.currentFloorFilter = val;
  const select = document.getElementById('floorSelect');
  if (select) select.value = val;

  buildingGroup.children.forEach(mesh => {
    if (val === 'ALL') {
      mesh.visible = true;
    } else {
      mesh.visible = mesh.userData.floor_index.toString() === val.toString();
    }
  });
}

function filterByCategory(category) {
  buildingGroup.children.forEach(mesh => {
    if (mesh.userData.category === category) {
      mesh.material.emissive = new THREE.Color(0xd4a853);
      mesh.material.emissiveIntensity = 0.4;
    } else {
      mesh.material.emissive = new THREE.Color(0x000000);
      mesh.material.emissiveIntensity = 0.0;
    }
  });
  setTimeout(() => {
    buildingGroup.children.forEach(mesh => {
      if (mesh !== StudioState.selectedMesh) {
        mesh.material.emissive = new THREE.Color(0x000000);
        mesh.material.emissiveIntensity = 0.0;
      }
    });
  }, 2000);
}

function toggleFloorVisibility(floorIdx, event) {
  if (event) event.stopPropagation();
  let anyVisible = false;
  buildingGroup.children.forEach(mesh => {
    if (mesh.userData.floor_index === floorIdx) {
      mesh.visible = !mesh.visible;
      anyVisible = mesh.visible;
    }
  });
}

function isolateSelectedElement() {
  if (!StudioState.selectedMesh) return;
  buildingGroup.children.forEach(mesh => {
    mesh.visible = mesh === StudioState.selectedMesh;
  });
}

/**
 * Camera Views & Visual Styles
 */
function setCameraView(viewName) {
  const target = controls.target;
  const dist = 24.0;

  // Update button active state
  ['btnViewIso', 'btnViewTop', 'btnViewFront', 'btnViewRight'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (viewName === 'iso') {
    camera.position.set(target.x + dist * 0.7, target.y + dist * 0.7, target.z + dist * 0.7);
    document.getElementById('btnViewIso')?.classList.add('active');
  } else if (viewName === 'top') {
    camera.position.set(target.x, target.y + dist * 1.2, target.z + 0.001);
    document.getElementById('btnViewTop')?.classList.add('active');
  } else if (viewName === 'front') {
    camera.position.set(target.x, target.y, target.z + dist);
    document.getElementById('btnViewFront')?.classList.add('active');
  } else if (viewName === 'right') {
    camera.position.set(target.x + dist, target.y, target.z);
    document.getElementById('btnViewRight')?.classList.add('active');
  } else if (viewName === 'left') {
    camera.position.set(target.x - dist, target.y, target.z);
  } else if (viewName === 'back') {
    camera.position.set(target.x, target.y, target.z - dist);
  }
  controls.update();
}

function setVisualStyle(style) {
  StudioState.visualStyle = style;
  ['btnStyleReal', 'btnStyleWire', 'btnStyleTrans'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  buildingGroup.children.forEach(mesh => {
    if (style === 'wireframe') {
      mesh.material.wireframe = true;
      mesh.material.transparent = false;
      mesh.material.opacity = 1.0;
    } else if (style === 'transparent') {
      mesh.material.wireframe = false;
      mesh.material.transparent = true;
      mesh.material.opacity = 0.35;
    } else {
      // Realistic PBR
      mesh.material.wireframe = false;
      mesh.material.transparent = mesh.userData.category === 'Window';
      mesh.material.opacity = mesh.userData.category === 'Window' ? 0.35 : 1.0;
    }
  });

  if (style === 'realistic') document.getElementById('btnStyleReal')?.classList.add('active');
  if (style === 'wireframe') document.getElementById('btnStyleWire')?.classList.add('active');
  if (style === 'transparent') document.getElementById('btnStyleTrans')?.classList.add('active');
}

function toggleGrid() {
  StudioState.showGrid = !StudioState.showGrid;
  gridHelper.visible = StudioState.showGrid;
}

function resetCamera() {
  setCameraView('iso');
}

/**
 * Drawing Upload Form Handler
 */
function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.add('hidden');
}

function displaySelectedFilename(input) {
  if (input.files && input.files[0]) {
    document.getElementById('uploadLabel').textContent = `Selected: ${input.files[0].name}`;
  }
}

async function handleDrawingUpload(event) {
  event.preventDefault();
  const form = document.getElementById('uploadDrawingForm');
  const fileInput = document.getElementById('fileInput');

  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Please select an architectural drawing file (DXF, PDF, PNG, JPG).');
    return;
  }

  const formData = new FormData(form);
  const statusMsg = document.getElementById('uploadStatusMsg');
  const statusText = document.getElementById('uploadStatusText');
  const btnSubmit = document.getElementById('btnSubmitUpload');

  statusMsg.classList.remove('hidden');
  btnSubmit.disabled = true;
  statusText.textContent = 'Uploading drawing and extracting architectural elements...';

  try {
    const res = await fetch('/api/studio/upload', {
      method: 'POST',
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Upload failed');
    }

    statusText.textContent = `Success! Generated 3D model with ${data.levels_count} floors. Loading viewport...`;

    setTimeout(async () => {
      closeUploadModal();
      statusMsg.classList.add('hidden');
      btnSubmit.disabled = false;
      await loadProject(data.project_id);
    }, 1200);

  } catch (err) {
    alert(`Error processing drawing: ${err.message}`);
    statusMsg.classList.add('hidden');
    btnSubmit.disabled = false;
  }
}

/**
 * 3D Model Export Actions
 */
function exportGLB() {
  const url = `/api/studio/projects/${StudioState.currentProjectId}/export/glb`;
  window.open(url, '_blank');
}

function exportOBJ() {
  const url = `/api/studio/projects/${StudioState.currentProjectId}/export/obj`;
  window.open(url, '_blank');
}

function roundTo(num, decimals) {
  const factor = Math.pow(10, decimals);
  return Math.round(num * factor) / factor;
}


// ============================================================================
// CONVERSATIONAL ARCHITECTURAL MODIFICATION ENGINE CONTROLLERS
// ============================================================================

let currentProposalData = null;

function setPromptAndFocus(promptText) {
  const input = document.getElementById('aiPromptInput');
  if (input) {
    input.value = promptText;
    input.focus();
  }
}

/**
 * Stage 1: Preview Architectural Proposal Before Applying
 */
async function previewModification() {
  const input = document.getElementById('aiPromptInput');
  const prompt = input ? input.value.trim() : '';
  if (!prompt) {
    alert('Please enter an architectural instruction (e.g. "Add 1 floor with 3 bedrooms and 1 washroom").');
    return;
  }

  const pill = document.getElementById('aiStatusPill');
  const statusText = document.getElementById('aiStatusText');
  const btnPreview = document.getElementById('btnAiPreview');

  pill?.classList.remove('hidden');
  if (statusText) statusText.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Analyzing constraints & formulating architectural proposal...</span>';
  if (btnPreview) btnPreview.disabled = true;

  try {
    const res = await fetch(`/api/studio/projects/${StudioState.currentProjectId}/preview-modification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to preview modification');

    currentProposalData = data;
    displayProposalModal(data);
  } catch (err) {
    alert(`Proposal generation failed: ${err.message}`);
  } finally {
    pill?.classList.add('hidden');
    if (btnPreview) btnPreview.disabled = false;
  }
}

function displayProposalModal(data) {
  const p = data.proposal;
  document.getElementById('propUserPrompt').textContent = `"${data.prompt}"`;
  document.getElementById('propOperation').textContent = (p.operation || 'MODIFICATION').toUpperCase();
  document.getElementById('propTargetElevation').textContent = p.target_floor || 'Level 02 (+3.00 m)';

  const tbody = document.getElementById('propRoomsTableBody');
  if (tbody) {
    tbody.innerHTML = '';
    const rooms = p.requested_rooms || [];
    document.getElementById('propRoomCountBadge').textContent = `${rooms.length} Rooms`;

    if (rooms.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="py-2 px-3 text-cad-muted text-center italic">No new enclosed rooms requested.</td></tr>';
    } else {
      rooms.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="py-2 px-3 font-medium text-white">${r.name || r.room_type}</td>
          <td class="py-2 px-3 font-mono text-cad-text">${r.width}m × ${r.length}m</td>
          <td class="py-2 px-3 font-mono text-desert text-right">${r.area} m²</td>
        `;
        tbody.appendChild(tr);
      });
    }
  }

  const val = p.validation || {};
  document.getElementById('propFootprintArea').textContent = `${val.building_footprint_sqm || 108.0} m²`;
  document.getElementById('propRequiredArea').textContent = `${val.required_rooms_area_sqm || 0.0} m²`;

  const chk = document.getElementById('propContainmentCheck');
  if (chk) {
    if (val.footprint_sufficient) {
      chk.className = 'text-emerald-400 font-semibold';
      chk.innerHTML = '<i class="fa-solid fa-circle-check mr-1"></i>PASSED (Sufficient floor area available)';
    } else {
      chk.className = 'text-rose-400 font-semibold';
      chk.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1"></i>EXCEEDS FOOTPRINT (Reduce rooms or expand)';
    }
  }

  const notesBox = document.getElementById('propNotesBox');
  if (notesBox) notesBox.textContent = p.notes || 'Layout will be generated deterministically within the building footprint.';

  document.getElementById('proposalModal')?.classList.remove('hidden');
}

function closeProposalModal() {
  document.getElementById('proposalModal')?.classList.add('hidden');
}

function confirmApplyProposal() {
  closeProposalModal();
  applyDirectModification();
}

/**
 * Stage 2: Directly Apply Natural Language Modification & Regenerate 3D Scene
 */
async function applyDirectModification() {
  const input = document.getElementById('aiPromptInput');
  const prompt = input ? input.value.trim() : '';
  if (!prompt) {
    alert('Please enter an architectural instruction.');
    return;
  }

  const pill = document.getElementById('aiStatusPill');
  const statusText = document.getElementById('aiStatusText');
  const btnApply = document.getElementById('btnAiApply');
  const btnPreview = document.getElementById('btnAiPreview');

  pill?.classList.remove('hidden');
  if (statusText) statusText.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Zoning layout, computing 3D geometry & updating building model...</span>';
  if (btnApply) btnApply.disabled = true;
  if (btnPreview) btnPreview.disabled = true;

  try {
    const res = await fetch(`/api/studio/projects/${StudioState.currentProjectId}/apply-modification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Modification failed');

    // 1. Update Global State
    StudioState.sceneData = data.scene;
    StudioState.bimTreeData = data.bim_tree;

    // 2. Regenerate Three.js 3D Viewport Meshes
    build3DScene(data.scene);

    // 3. Update Left Panel BIM Tree
    renderBIMTree(data.bim_tree);

    // 4. Update Story dropdown options
    updateFloorFilterOptions(data.scene.levels);

    // 5. Update Revision badge
    if (data.history) updateRevisionBadge(data.history);

    // 6. Provide clear visual confirmation
    if (statusText) {
      statusText.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i><span class="text-white">${data.message || 'Building modified successfully!'} (${data.scene.total_mesh_count} meshes)</span>`;
    }

    setTimeout(() => {
      pill?.classList.add('hidden');
    }, 4500);

  } catch (err) {
    alert(`Error applying architectural modification: ${err.message}`);
    pill?.classList.add('hidden');
  } finally {
    if (btnApply) btnApply.disabled = false;
    if (btnPreview) btnPreview.disabled = false;
  }
}

/**
 * Undo Last Modification
 */
async function undoModification() {
  try {
    const res = await fetch(`/api/studio/projects/${StudioState.currentProjectId}/undo`, {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Cannot undo further.');
      return;
    }

    StudioState.sceneData = data.scene;
    StudioState.bimTreeData = data.bim_tree;
    build3DScene(data.scene);
    renderBIMTree(data.bim_tree);
    updateFloorFilterOptions(data.scene.levels);
    if (data.history) updateRevisionBadge(data.history);

  } catch (err) {
    console.error('Undo failed:', err);
  }
}

/**
 * Redo Next Modification
 */
async function redoModification() {
  try {
    const res = await fetch(`/api/studio/projects/${StudioState.currentProjectId}/redo`, {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Cannot redo further.');
      return;
    }

    StudioState.sceneData = data.scene;
    StudioState.bimTreeData = data.bim_tree;
    build3DScene(data.scene);
    renderBIMTree(data.bim_tree);
    updateFloorFilterOptions(data.scene.levels);
    if (data.history) updateRevisionBadge(data.history);

  } catch (err) {
    console.error('Redo failed:', err);
  }
}

function updateRevisionBadge(history) {
  const badge = document.getElementById('revisionBadge');
  const btnUndo = document.getElementById('btnUndo');
  const btnRedo = document.getElementById('btnRedo');

  if (badge) {
    badge.textContent = `v${history.current_index + 1}`;
    badge.title = `Current Revision: ${history.current_index + 1} of ${history.total_revisions}`;
  }

  if (btnUndo) {
    btnUndo.disabled = !history.can_undo;
    btnUndo.classList.toggle('opacity-40', !history.can_undo);
    btnUndo.classList.toggle('cursor-not-allowed', !history.can_undo);
  }

  if (btnRedo) {
    btnRedo.disabled = !history.can_redo;
    btnRedo.classList.toggle('opacity-40', !history.can_redo);
    btnRedo.classList.toggle('cursor-not-allowed', !history.can_redo);
  }
}

/**
 * Room Dimension Library Modal Controls
 */
async function openRoomSettingsModal() {
  document.getElementById('roomSettingsModal')?.classList.remove('hidden');
  try {
    const res = await fetch('/api/studio/room-library');
    if (res.ok) {
      const data = await res.json();
      const dims = data.standard_dimensions || {};
      if (dims.bedroom) {
        document.getElementById('lib_bedroom_w').value = dims.bedroom.default_width_m;
        document.getElementById('lib_bedroom_l').value = dims.bedroom.default_length_m;
      }
      if (dims.master_bedroom) {
        document.getElementById('lib_master_w').value = dims.master_bedroom.default_width_m;
        document.getElementById('lib_master_l').value = dims.master_bedroom.default_length_m;
      }
      if (dims.washroom) {
        document.getElementById('lib_washroom_w').value = dims.washroom.default_width_m;
        document.getElementById('lib_washroom_l').value = dims.washroom.default_length_m;
      }
      if (dims.living) {
        document.getElementById('lib_living_w').value = dims.living.default_width_m;
        document.getElementById('lib_living_l').value = dims.living.default_length_m;
      }
      if (dims.kitchen) {
        document.getElementById('lib_kitchen_w').value = dims.kitchen.default_width_m;
        document.getElementById('lib_kitchen_l').value = dims.kitchen.default_length_m;
      }
    }
  } catch (err) {
    console.warn('Could not fetch room library standards:', err);
  }
}

function closeRoomSettingsModal() {
  document.getElementById('roomSettingsModal')?.classList.add('hidden');
}

function saveRoomSettings() {
  closeRoomSettingsModal();
  const pill = document.getElementById('aiStatusPill');
  const statusText = document.getElementById('aiStatusText');
  if (pill && statusText) {
    pill.classList.remove('hidden');
    statusText.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i><span>Room dimension standards updated! Next modifications will use these measurements.</span>';
    setTimeout(() => pill.classList.add('hidden'), 3500);
  }
}
