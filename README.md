# ABCBooks

## Project Description

The ABC Books project makes available for research and analysis an interactive digital archive of rare children’s alphabet books. The overarching goal of the project is for students not only to use the archive as a research resource but also actively to build and enhance it. The archive was made available to the Spring 2016 Children’s Literature students at Princeton University. During the semester students were given opportunities to work with the archive and help us develop a more robust search function. Each student in the course added 100 “tags” to the archive, describing what they saw in the imagery, styles, and concepts of the ABC Books. 

## Project Development

The project was built upon the Drupal content management system. Images of the ABC books contained in the archive are transcluded from the Princeton University Digital Library (PUDL). The archive makes use of Internet Archive BookReader code for the dsiplay of page images:

http://openlibrary.org/dev/docs/bookreader

https://github.com/internetarchive/bookreader

###XML

The XML (TEI) transcriptions of the books are included in this repository were created by the project participants with help from the students in the Children's Literature course. The TEI files are hosted with accompanying XQuery files on a Princeton University owned [eXistdb](http://exist-db.org/exist/apps/homepage/index.html) server.

###Additional Drupal Modules

[Flag Bookmarking module](https://www.drupal.org/project/flag) For saving bookmarks of page images for display in the users' profile pages.

BookTags. A custom module for the collection of tags associated with book page images.

[Views](https://www.drupal.org/project/views) The archive makes extensive use of the Views module. 

## Links

[ABCBooks](http://etc.princeton.edu/abcbooks)

[Princeton University Digital Library](http://pudl.princeton.edu/)

[McGraw Center for Teaching and Learning](http://mcgraw.princeton.edu)

[Center for Digital Humanities](http://digitalhumanities.princeton.edu)
