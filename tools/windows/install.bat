@echo off
rem Installe les prérequis d'IDEmu pour Windows (demande les droits administrateur).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"%~dp0install.ps1\"'"
