'use strict';
window.addEventListener('load', async function() {
  // Initial setup
  const body = d3.select('body');
  const svg = d3.select('#tree');
  const links = svg.select('#links');
  const labels = svg.select('#labels');
	const data = await fetch('data.json').then(r => r.json());
  const idx = lunr(function () {
    this.ref('id');
    this.field('name');
    this.field('description');
    this.field('countries');

    data.filter(cand => cand).forEach(cand => this.add(cand));
  });

  function render(root) {
    // Compute dag and filter
    const unfiltered = d3.dagHierarchy()
      .children(d => d.advisors.map(a => data[a]))
      (root);
    unfiltered.eachAfter(n => n.data.maxScore = Math.max(n.data.score, ...n.children.map(c => c.data.maxScore)));
    const dag = d3.dagHierarchy()
      .children(d => d.advisors.map(a => data[a]).filter(d => d.maxScore))
      (root);

    // Update classes and url
    window.location.hash = `#${root.id}`;
    body.attr('class', 'treeing');

    // Display
    const { width, height } = svg.node().getBoundingClientRect();

    const color = d3.scaleLinear().domain([0, root.maxScore]).range(['#FFECB3', '#FF6F00']);

    const labs = labels.selectAll('a').data(dag.nodes())
      .enter().append('a')
      .attr('target', '_blank')
      .attr('rel', 'noopener')
      .attr('href', ({ data }) => data.wikiLink);
    const rects = labs.append('rect')
      .style('stroke', ({ data }) => data.wikiLink ? color(data.score) : '#000')
      .style('fill', ({ data }) => data.wikiLink ? color(data.score) : '#000');
    const texts = labs.append('text').text(({ data }) => data.shortName);

    const dims = texts.nodes().map(d => d.getBBox()).map(({width, height}) => ({width: width / 2, height: height / 2}));
    const rectDims = rects
      .style('x', (_, i) => `calc(${-dims[i].width}px - 0.25rem)`)
      .style('y', (_, i) => `calc(${-dims[i].height}px - 0.25rem)`)
      .style('width', (_, i) => `calc(${dims[i].width}px * 2 + 0.5rem)`)
      .style('height', (_, i) => `calc(${dims[i].height}px * 2 + 0.5rem)`)
      .nodes().map(n => n.getBoundingClientRect());
    dag.nodes().forEach((node, i) => {
      node.data.width = rectDims[i].width;
      node.data.height = rectDims[i].height;
    });
    let { extraWidth, extraHeight } = rectDims.reduce(
        ({extraWidth, extraHeight}, {width, height}) => ({extraWidth: Math.max(width, extraWidth), extraHeight: Math.max(height, extraHeight)}),
        {extraWidth: 0, extraHeight: 0});
    // XXX This is necessary since z-index isn't supported yet
    labs.on('mouseover', function () {
      const dthis = d3.select(this).raise();
    });

    d3.dagLayout().size([width - extraWidth, height - extraHeight])(dag);

    labs.attr('transform', ({x, y}) => `translate(${x}, ${-y})`);
    const line = d3.line().curve(d3.curveCatmullRom).x(d => d.x).y(d => -d.y);
    links.selectAll('g').data(dag.links())
      .enter().append('g')
      .append('path')
      // XXX d3 linkVertical isn't working as intended...
      .attr('d', ({ source, target }) => `M${source.x},${-source.y}C${source.x},${(-source.y - target.y) / 2} ${target.x},${(-source.y - target.y) / 2} ${target.x},${-target.y}`);

    const bbox = svg.node().getBBox();
    svg.attr('viewBox', [-extraWidth / 2, extraHeight / 2 - height, width, height].join(' '));
    labs.classed('rendered', true)
  }

  // Add filtering
  const candidates = d3.select('#candidates');
  const input = d3.select('#search-box input');
  input.on('input', () => {
    const string = input.node().value;
    if (lunr.tokenizer(string).length) {
      const results = idx.search(string).slice(0, 20).map(({ ref }) => data[parseInt(ref)]);
      candidates.html('');
      results.forEach((cand) => {
        candidates.append('li').classed('mdc-list-item', true)
          .on('click', () => render(cand))
          .append('span').classed('mdc-list-item__text', true).text(cand.name)
          .append('span').classed('mdc-list-item__secondary-text', true)
          .text(cand.description);
      });
    } else {
      candidates.html('');
    }
  });

  // Search button reset
  d3.select('#search-button').on('click', () => {
    body.attr('class', 'searching');
    links.html('');
    labels.html('');
  });

  // Info
  const info = new mdc.dialog.MDCDialog(document.querySelector('#info'));
  d3.select('#info-button').on('click', () => info.show());

  // Initialize
  const init = data[parseInt(window.location.hash.slice(1))];
  if (init && init.id) {
    render(init);
  } else {
    body.attr('class', 'searching');
  }
});
