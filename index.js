const lunr = require('lunr');
const fs = require('fs');

const data = JSON.parse(fs.readFileSync(0, {encoding: 'utf8'}));
const idx = lunr(function () {
  this.ref('id');
  this.field('name');
  this.field('description');
  this.field('countries');

  data.filter((cand) => cand).forEach(cand => this.add(cand));
});
fs.appendFileSync(1, JSON.stringify(idx), {encoding: 'utf8'})
