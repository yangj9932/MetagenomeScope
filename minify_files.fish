#! /usr/bin/fish
# Minifies the custom JavaScript and CSS code in MetagenomeScope.
#
# Assumes that both csso-cli and uglify-js have been installed through NPM
# with the -g option enabled.
set -l attribution "/* Copyright (C) 2017-2018 Marcus Fedarko, Jay Ghurye, Todd Treangen, Mihai Pop
 * Authored by Marcus Fedarko
 *
 * This file is part of MetagenomeScope.
 *
 * MetagenomeScope is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * MetagenomeScope is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with MetagenomeScope.  If not, see <http://www.gnu.org/licenses/>.
 */"
echo $attribution > viewer/js/xdot2cy.min.js
echo $attribution > viewer/css/viewer_style.min.css
csso viewer/css/viewer_style.css >> viewer/css/viewer_style.min.css
uglifyjs viewer/js/xdot2cy.js >> viewer/js/xdot2cy.min.js