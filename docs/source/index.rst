.. FoodScrappy documentation master file, created by
   sphinx-quickstart on Wed Jul 29 21:27:28 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

FoodScrappy documentation
=========================

FoodScrappy is a restaurant enrichment CLI that reads restaurant CSV files and
finds official websites, social profiles, and delivery platform links using
Google Places and Brave Search.

Quick usage
-----------

.. code-block:: powershell

   python -m scrappy enrich restaurants.csv --out enriched_restaurants.csv --region ES


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api

