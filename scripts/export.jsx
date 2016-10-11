// This script automates exporting to designated directories.
//
// Due to Adobe's very limited budget, we aren't able to do things like
// export to relative paths in a recorded action or set the slice export
// directory.  I hope Adobe starts a kickstarter campaign so they have the
// resources to address these issues and maybe add a history panel to
// Illustrator one day.

function vimmerMain() {
  var doc = activeDocument;
  var baseDir = doc.fullName.path;
  var baseName = doc.fullName.name;


  function forEach(array, func) {
    for (var i = 0, l = array.length; i < l; i++) {
      if (func(array[i], i, array) === false) {
        break;
      }
    }
  }

  function setArtboard(name) {
    for (var i = 0; i < doc.artboards.length; i++) {
      if (doc.artboards[i].name == name) {
        doc.artboards.setActiveArtboardIndex(i);
        return doc.artboards[i];
      }
    }
  }

  function isUsable(item) {
    while (item.parent) {
      if (item.hidden || item.guides) {
        return false;
      }

      if (item.parent.typename == 'CompoundPathItem') {
        return false;
      }

      item = item.parent;
    }

    return true;
  }

  function arrayContains(array, item) {
    var found = false;
    forEach(array, function(aitem) {
      if (item === aitem) {
        found = true;
        return false;
      }
    });

    return found;
  }

  function duplicateArtboardAsDoc(name) {
    app.activeDocument = doc;

    var artboard = setArtboard(name);
    var bounds = artboard.artboardRect;
    var newDoc = app.documents.add(DocumentColorSpace.RGB, 1, 1);

    app.activeDocument = newDoc;

    forEach(doc.pageItems, function(item) {
      if (rectIntersects(bounds, item.geometricBounds) && isUsable(item)) {
        var newItem = item.duplicate(newDoc, ElementPlacement.PLACEATEND);
        newItem.name = item.name;
      }
    });

    newDoc.layers[0].name = name;
    newDoc.artboards[0].artboardRect = bounds;

    return newDoc;
  }

  function removeDoc(remDoc) {
    if (doc == remDoc) {
      return;
    }

    remDoc.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
  }

  function exportSVG(name) {
    var dupe = duplicateArtboardAsDoc(name);
    var options = new ExportOptionsSVG();
    options.compressed = false;
    options.coordinatePrecision = 3;
    options.cssProperties = SVGCSSPropertyLocation.PRESENTATIONATTRIBUTES;
    options.documentEncoding = SVGDocumentEncoding.UTF8;
    options.embedRasterImages = false;
    options.includeFileInfo = false;
    options.preserveEditability = false;
    options.saveMultipleArtboards = false;

    var file = new File(baseDir + '/source/' + name.toLowerCase() + '.svg');
    if (file.exists) {
      file.remove();
    }

    dupe.exportFile(file, ExportType.SVG, options);
    removeDoc(dupe);
  }

  function exportPalettePNG(swatchDoc, swatch) {
    var artboardIndex = swatchDoc.artboards.getActiveArtboardIndex();
    swatchDoc.artboards.add(swatch.geometricBounds);
    var artboardIndex2 = swatchDoc.artboards.getActiveArtboardIndex();

    var options = new ExportOptionsPNG24();
    options.antiAliasing = false;
    options.artBoardClipping = true;
    options.transparency = false;

    var file = new File(baseDir + '/.meta/' + swatch.name + '.png');
    swatchDoc.exportFile(file, ExportType.PNG24, options);

    swatchDoc.artboards.remove(artboardIndex2);
    swatchDoc.artboards.setActiveArtboardIndex(artboardIndex);
  }

  function rectIntersects(r1, r2) {
    // Note: The Y axis is inverted.
    return !(
      r2[0] > r1[2] ||
      r2[2] < r1[0] ||
      r2[1] < r1[3] ||
      r2[3] > r1[1]
    );
  }

  function exportPalette() {
    var dupe = duplicateArtboardAsDoc('Notes');
    var bounds = dupe.artboards[0].artboardRect;

    forEach(dupe.pathItems, function(item, i, array) {
      if (item.name != '' && item.name.charAt(0) != '<' && item.typename == 'PathItem' && rectIntersects(bounds, item.geometricBounds)) {
        exportPalettePNG(dupe, item);
      }
    });

    removeDoc(dupe);
  }

  exportSVG('Logo');
  exportSVG('Icon');
  exportPalette();
}

vimmerMain();

// vim: set ft=javascript ts=2 sw=2 tw=0 et :
